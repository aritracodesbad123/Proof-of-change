"""Two-arm benchmark runner: each manifest case through the product check path, in Contree only.

    python -m bench.run --cases bench/cases [--case ID ...] [--swarm-arm] [--out bench/results/<date>]

Arms (same commits, same Contree backend, same timeouts; only what decides the verdict differs):
  tests          --baseline tests, --model-provider none (test comparison only; no model calls)
  tests+probes   --baseline tests+probes, --model-provider nebius (adds model-written claim probes)
  tests+probes+swarm   (with --swarm-arm) the same plus --swarm (advisory; must not change the verdict)

Every run is `ops/daily_run.py --pr URL --product-check --sandbox-backend contree` with POC_REQUIRE_CONTREE=1, so
a missing Contree setup refuses instead of falling back to local. Nothing is posted anywhere. One JSON result per
case and arm is written to OUT/<arm>/<case id>.json; the check's own record and logs stay under OUT/ops/.
A case whose check did not produce a record, or tested different commits than the manifest names, gets
outcome "not_run" (the summary counts it as a miss, never a win). Fixture cases are refused.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bench.manifest import load_cases

REPO_ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))
ARMS = {
    "tests": ["--baseline", "tests", "--model-provider", "none"],
    "tests+probes": ["--baseline", "tests+probes", "--model-provider", "nebius"],
    "tests+probes+swarm": ["--baseline", "tests+probes", "--model-provider", "nebius", "--swarm"],
}
KEY_NAMES = ("NEBIUS_API_KEY", "NEBIUS_PROJECT_ID", "GITHUB_POC_TOKEN")  # reported only as set/unset
SECRET_NAMES = KEY_NAMES + ("TAVILY_API_KEY", "POC_SMTP_PASSWORD")


def redact(text: str, env=None) -> str:
    """Remove the value of every secret environment variable from text before it is saved."""
    env = os.environ if env is None else env
    for k in SECRET_NAMES:
        v = env.get(k)
        if v and len(v) >= 4:
            text = text.replace(v, f"[{k} redacted]")
    return text


def arm_dir_name(arm: str) -> str:
    return arm.replace("+", "_")


def command(case: dict, arm: str, ops_dir: Path, run_name: str) -> list[str]:
    return [sys.executable, str(REPO_ROOT / "ops" / "daily_run.py"), "--pr", case["pr_url"], "--product-check",
            "--sandbox-backend", "contree", *ARMS[arm], "--ops-dir", str(ops_dir), "--date", run_name, "--no-report"]


def find_record(ops_dir: Path, run_name: str) -> dict | None:
    recs = sorted((ops_dir / "runs" / run_name).glob("*/record.json"))
    if len(recs) != 1:
        return None
    try:
        return json.loads(recs[0].read_text())
    except (OSError, ValueError):
        return None


def stages(rec: dict | None, exit_code: int | None) -> dict:
    """Stage states derived from the check's record (derived here, not new fields of the record)."""
    if rec is None:
        return {"infra": "failed" if exit_code not in (0, None) else "no_record", "install": "unknown",
                "tests": "not_run", "probes": "not_run"}
    ic = rec.get("installed_commit") or {}
    sides = [v for v in ic.values() if isinstance(v, dict)]
    runs = rec.get("per_run") or []
    reason = str(rec.get("reason") or "")
    if sides and all(s.get("ok") for s in sides):
        install = "ok"
    elif (sides and not all(s.get("ok") for s in sides)) or "install failed" in reason or "build failed" in reason:
        install = "failed"
    else:
        install = "unknown"
    ran = any((r.get("passed") or 0) + (r.get("failed") or 0) > 0 for r in runs)
    probes = (rec.get("probes") or {}).get("status") or "off"
    return {"infra": "ok", "install": install, "tests": "ran" if ran else "not_run", "probes": probes}


def sha_check(case: dict, rec: dict | None) -> list[str]:
    """Problems with the commits the check actually tested versus the manifest."""
    if rec is None:
        return []
    sides = rec.get("sides") or {}
    main_sha = sides.get("main_sha")
    head = (rec.get("chosen") or {}).get("head_sha") or rec.get("current_head_sha")
    p = []
    if head != case["head_sha"]:
        p.append(f"tested PR head {head} is not the manifest head_sha")
    if main_sha != case["base_sha"]:
        p.append(f"tested base {main_sha} is not the manifest base_sha")
    if main_sha and head and main_sha == head:
        p.append("base and PR head are the same commit")
    return p


def result_for(case: dict, arm: str, cmd: list[str], rec: dict | None, exit_code: int | None, seconds: float,
               stderr_tail: str = "") -> dict:
    problems = sha_check(case, rec)
    ran = rec is not None and not problems and rec.get("verdict") is not None
    cost = (rec or {}).get("cost") or {}
    return {
        "schema": "poc-bench-result/1", "case_id": case["id"], "arm": arm, "fixture": bool(case.get("fixture")),
        "category": case["category"], "expected_verdict": case["expected_verdict"],
        "outcome": "ran" if ran else "not_run", "verdict": rec.get("verdict") if ran else None,
        "reason": (rec or {}).get("reason"), "not_run_why": None if ran else (problems or [f"no usable record (exit {exit_code})"]),
        "stages": stages(rec, exit_code), "wall_seconds": round(seconds, 1),
        "check_duration_s": (rec or {}).get("duration_s"),
        "model": {"ai_calls": cost.get("ai_calls"), "failed_ai_calls": cost.get("failed_ai_calls"),
                  "input_tokens": cost.get("input_tokens"), "output_tokens": cost.get("output_tokens"),
                  "cost_usd": cost.get("cost_usd"), "provider": (rec or {}).get("model_provider")},
        "tested": {"base_sha": ((rec or {}).get("sides") or {}).get("main_sha"),
                   "pr_sha": ((rec or {}).get("sides") or {}).get("pr_sha"),
                   "head_sha": ((rec or {}).get("chosen") or {}).get("head_sha")},
        "command": [Path(cmd[0]).name, *cmd[1:]], "exit_code": exit_code, "stderr_tail": redact(stderr_tail[-2000:]),
        "record_id": (rec or {}).get("id"), "poc_commit": (rec or {}).get("poc_commit"),
    }


def environment() -> dict:
    try:
        head = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        head = None
    return {"python": platform.python_version(), "platform": platform.platform(), "harness_commit": head,
            "sandbox_backend": "contree", "POC_REQUIRE_CONTREE": "1",
            "keys": {k: ("set" if os.environ.get(k) else "unset") for k in KEY_NAMES},
            "started_ist": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")}


def run_one(case: dict, arm: str, out: Path, execute=subprocess.run) -> dict:
    ops_dir = out / "ops" / arm_dir_name(arm)
    run_name = f"bench-{case['id']}"
    cmd = command(case, arm, ops_dir, run_name)
    env = dict(os.environ, POC_REQUIRE_CONTREE="1")
    t0 = time.time()
    try:
        p = execute(cmd, env=env, capture_output=True, text=True, check=False)
        code, err = p.returncode, p.stderr or ""
    except OSError as e:
        code, err = None, f"could not start: {e}"
    res = result_for(case, arm, cmd, find_record(ops_dir, run_name), code, time.time() - t0, err)
    d = out / arm_dir_name(arm)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{case['id']}.json").write_text(json.dumps(res, indent=1))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", default=str(REPO_ROOT / "bench" / "cases"))
    ap.add_argument("--case", action="append", default=[], help="limit to these case ids")
    ap.add_argument("--swarm-arm", action="store_true", help="also run the tests+probes+swarm arm")
    ap.add_argument("--out", default=None, help="default bench/results/<today IST>")
    a = ap.parse_args(argv)
    cases, problems = load_cases(Path(a.cases))
    if problems:
        for f, ps in problems.items():
            print(f"{f}: {'; '.join(ps)}", file=sys.stderr)
        return 1
    cases = [c for c in cases if not a.case or c["id"] in a.case]
    if any(c.get("fixture") for c in cases):
        print("refusing: fixture cases are for unit tests, not benchmark results", file=sys.stderr)
        return 1
    if not cases:
        print("no cases to run", file=sys.stderr)
        return 1
    out = Path(a.out or REPO_ROOT / "bench" / "results" / datetime.now(IST).strftime("%Y-%m-%d"))
    out.mkdir(parents=True, exist_ok=True)
    arms = ["tests", "tests+probes"] + (["tests+probes+swarm"] if a.swarm_arm else [])
    (out / "run_meta.json").write_text(json.dumps({"environment": environment(), "arms": {k: ARMS[k] for k in arms},
                                                   "cases": [c["id"] for c in cases]}, indent=1))
    for c in cases:
        for arm in arms:
            r = run_one(c, arm, out)
            print(f"{c['id']} [{arm}]: {r['verdict'] or 'NOT RUN'} ({r['wall_seconds']} s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
