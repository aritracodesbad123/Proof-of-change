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
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bench.manifest import load_cases
from poc.contree_sandboxes import KEY_ENV as CONTREE_KEY_ENV
from poc.contree_sandboxes import PROJECT_ENV as CONTREE_PROJECT_ENV

REPO_ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))
ARMS = {
    "tests": ["--baseline", "tests", "--model-provider", "none"],
    "tests+probes": ["--baseline", "tests+probes", "--model-provider", "nebius"],
    "tests+probes+swarm": ["--baseline", "tests+probes", "--model-provider", "nebius", "--swarm"],
}
KEY_NAMES = ("NEBIUS_API_KEY", "NEBIUS_PROJECT_ID", "GITHUB_POC_TOKEN")  # reported only as set/unset
SECRET_NAMES = tuple(dict.fromkeys(KEY_NAMES + ("TAVILY_API_KEY", "POC_SMTP_PASSWORD", "GH_TOKEN", "GITHUB_TOKEN",
                                                 CONTREE_KEY_ENV, CONTREE_PROJECT_ENV)))
RED_LABELS = ("false_claim", "unmentioned")  # probe findings that make a verdict needs_attention
PROBE_RUNS = 3


def redact(text: str, env=None) -> str:
    """Remove the value of every secret environment variable from text before it is saved."""
    env = os.environ if env is None else env
    for k in SECRET_NAMES:
        v = env.get(k)
        if v and len(v) >= 4:
            text = text.replace(v, f"[{k} redacted]")
    return text


def redact_all(obj, env=None):
    """redact() applied to every string in a JSON-like object, keys included."""
    if isinstance(obj, str):
        return redact(obj, env)
    if isinstance(obj, dict):
        return {redact_all(k, env): redact_all(v, env) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_all(v, env) for v in obj]
    return obj


def probe_held(rec: dict | None) -> bool | None:
    """True when a probe finding (false claim or unmentioned change) showed the same main and PR values on all
    PROBE_RUNS runs of each side; False when the record shows probe runs but no such finding; None when the record
    does not expose per-run probe values."""
    items = ((rec or {}).get("probes") or {}).get("items")
    if not isinstance(items, list) or not items:
        return None
    exposed = False
    for it in items:
        runs = it.get("runs") if isinstance(it, dict) else None
        if not isinstance(runs, dict) or not isinstance(it.get("observations"), list):
            continue
        exposed = True
        sides = {k: runs.get(k) for k in ("main", "pr")}
        if not all(isinstance(v, list) and len(v) == PROBE_RUNS for v in sides.values()):
            continue
        if not all(r.get("ok") for r in it.get("per_run") or [{}]):
            continue
        for o in it["observations"]:
            name = o.get("name")
            if o.get("state") != "differs" or o.get("label") not in RED_LABELS:
                continue
            vals = {k: [r.get(name, "<missing>") if isinstance(r, dict) else "<missing>" for r in v] for k, v in sides.items()}
            if all(len({json.dumps(x, sort_keys=True) for x in v}) == 1 for v in vals.values()) and vals["main"][0] != vals["pr"][0]:
                return True
    return False if exposed else None


def arm_dir_name(arm: str) -> str:
    return arm.replace("+", "_")


def command(case: dict, arm: str, ops_dir: Path, run_name: str) -> list[str]:
    return [sys.executable, str(REPO_ROOT / "ops" / "daily_run.py"), "--pr", case["pr_url"], "--product-check",
            "--sandbox-backend", "contree", *ARMS[arm], "--ops-dir", str(ops_dir), "--date", run_name, "--no-report",
            *(["--base-sha", case["base_sha"], "--head-sha", case["head_sha"]]
              if case.get("base_sha") and case.get("head_sha") else [])]


TRANSPORT_ERROR = "ContreeTransportError"


def transport_failed(rec: dict | None) -> bool:
    """True only when Contree itself could not be reached (a network/transport error before any test ran).
    A test failure, a setup gap or any verdict from tests that did run is never a reason to retry."""
    failed = ((rec or {}).get("contree") or {}).get("failed") or ""
    return TRANSPORT_ERROR in str(failed)


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


def pr_side(case: dict, sides: dict) -> tuple[str | None, list[str]]:
    """How the PR side was tested: "head" (the PR head itself) or "merge_ref" (GitHub's test merge commit, accepted
    only when it is exactly base_sha + head_sha). Returns (kind or None, problems)."""
    if sides.get("pr_sha") == case["head_sha"]:
        return "head", []
    if "merge_commit" not in sides:
        return None, [f"tested PR side {sides.get('pr_sha')} is not the manifest head_sha"]
    p = []
    if not sides.get("merge_commit") or sides.get("pr_sha") != sides.get("merge_commit"):
        p.append("tested PR side is neither head_sha nor the recorded merge commit")
    if sides.get("merge_parents") != [case["base_sha"], case["head_sha"]]:
        p.append(f"merge commit parents {sides.get('merge_parents')} are not [base_sha, head_sha]")
    if sides.get("main_sha") != case["base_sha"]:
        p.append("merge-ref comparison base is not base_sha")
    if sides.get("merge_head_matches_pinned_head") is not True:
        p.append("merge commit's PR parent does not match the pinned head")
    return (None, p) if p else ("merge_ref", [])


def sha_check(case: dict, rec: dict | None) -> list[str]:
    """Problems with the commits the check actually tested versus the manifest."""
    if rec is None:
        return []
    sides = rec.get("sides") or {}
    main_sha = sides.get("main_sha")
    head = (rec.get("chosen") or {}).get("head_sha")
    p = []
    if not head:
        p.append("tested PR head unknown")
    elif head != case["head_sha"]:
        p.append(f"tested PR head {head} is not the manifest head_sha")
    # A moved live PR head is information only (kept in the result as head_moved / current_head_sha):
    # the check tested the pinned commits, so only a mismatch in the tested commits marks a case not run.
    p += pr_side(case, sides)[1]
    if main_sha != case["base_sha"]:
        p.append(f"tested base {main_sha} is not the manifest base_sha")
    if main_sha and head and main_sha == head:
        p.append("base and PR head are the same commit")
    return p


def contree_check(rec: dict | None) -> list[str]:
    """The record must show the check really ran in Contree (backend contree and both checkpoints built there)."""
    if rec is None:
        return []
    if rec.get("sandbox_backend") != "contree" or rec.get("machine") != "contree":
        return [f"record does not show a Contree run (sandbox_backend={rec.get('sandbox_backend')!r}, "
                f"machine={rec.get('machine')!r})"]
    return []


def result_for(case: dict, arm: str, cmd: list[str], rec: dict | None, exit_code: int | None, seconds: float,
               stderr_tail: str = "") -> dict:
    problems = sha_check(case, rec) + contree_check(rec)
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
        "head_moved": bool((rec or {}).get("head_moved")),
        "current_head_sha": (rec or {}).get("current_head_sha"),
        "tested": {"base_sha": ((rec or {}).get("sides") or {}).get("main_sha"),
                   "pr_sha": ((rec or {}).get("sides") or {}).get("pr_sha"),
                   "head_sha": ((rec or {}).get("chosen") or {}).get("head_sha"),
                   "pr_side": pr_side(case, (rec or {}).get("sides") or {})[0] if rec else None},
        "command": [Path(cmd[0]).name, *cmd[1:]], "exit_code": exit_code, "stderr_tail": stderr_tail[-2000:],
        "record_id": (rec or {}).get("id"), "poc_commit": (rec or {}).get("poc_commit"),
        "sandbox": {"backend": (rec or {}).get("sandbox_backend"), "machine": (rec or {}).get("machine")},
        "probe_held_all_runs": probe_held(rec),
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
    retried = False
    for attempt in (1, 2):
        try:
            p = execute(cmd, env=env, capture_output=True, text=True, check=False)
            code, err = p.returncode, p.stderr or ""
        except OSError as e:
            code, err = None, f"could not start: {e}"
        rec = find_record(ops_dir, run_name)
        if attempt == 1 and transport_failed(rec):
            retried = True
            shutil.rmtree(ops_dir / "runs" / run_name, ignore_errors=True)  # the retry writes a fresh record
            continue
        break
    res = redact_all(result_for(case, arm, cmd, rec, code, time.time() - t0, err))
    res["retried_after_contree_transport_error"] = retried
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
    meta = {"environment": environment(), "arms": {k: ARMS[k] for k in arms},
            "cases": [{"id": c["id"], "category": c["category"], "expected_verdict": c["expected_verdict"],
                       "fixture": bool(c.get("fixture"))} for c in cases]}
    (out / "run_meta.json").write_text(json.dumps(redact_all(meta), indent=1))
    for c in cases:
        for arm in arms:
            r = run_one(c, arm, out)
            print(f"{c['id']} [{arm}]: {r['verdict'] or 'NOT RUN'} ({r['wall_seconds']} s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
