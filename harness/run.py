"""Run one Blast Radius tuple through the runner (br_run.py) with the guardrails applied.

    python -m harness.run --upstream pandas --old 2.3.3 --new 3.0.0rc0 --dependent UpSetPlot \
        --tests repo:https://github.com/jnothman/UpSetPlot:upsetplot/tests --expected "break: ..." \
        --expected-class break

All arguments after the wrapper's own are passed to br_run.py unchanged, except that:
  * --runs is forced to 3 (the protocol); other values are refused,
  * --root defaults to ./data so records and runs stay inside this repo's ignored data dir,
  * the single-thread env vars are forced, and --machine is set from the detected machine type.
After the runner finishes, the record gets `machine_type` and `thread_env`, is schema-validated,
and is rewritten in place (record.json and the last line of observations.jsonl).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from guardrails.isolation import SINGLE_THREAD_ENV, single_thread_env
from guardrails.schema import REQUIRED_RUNS_PER_SIDE, validate_record
from harness.machine import detect_machine_type

REPO = Path(__file__).resolve().parent.parent


def find_runner() -> Path:
    for cand in (os.environ.get("BR_RUNNER"), REPO / "harness" / "br_run.py"):
        if cand and Path(cand).is_file():
            return Path(cand)
    raise SystemExit("br_run.py not found: set BR_RUNNER or add harness/br_run.py (the runner)")


def build_command(runner: Path, passthrough: list[str], root: Path, machine: dict) -> list[str]:
    if "--runs" in passthrough:
        i = passthrough.index("--runs")
        if passthrough[i + 1] != str(REQUIRED_RUNS_PER_SIDE):
            raise SystemExit(f"--runs must be {REQUIRED_RUNS_PER_SIDE} (protocol: 3 alternating runs per side)")
    cmd = [sys.executable, str(runner), *passthrough]
    if "--runs" not in passthrough:
        cmd += ["--runs", str(REQUIRED_RUNS_PER_SIDE)]
    if "--root" not in passthrough:
        cmd += ["--root", str(root)]
    if "--machine" not in passthrough:
        cmd += ["--machine", machine["label"]]
    return cmd


def enrich(rec: dict, machine: dict) -> dict:
    rec = dict(rec)
    rec["machine_type"] = machine
    rec["thread_env"] = dict(SINGLE_THREAD_ENV)
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", default=str(REPO / "data"))
    ap.add_argument("--dry-run", action="store_true", help="print the command and exit")
    own, passthrough = ap.parse_known_args(argv)
    root = Path(own.data_root)
    machine = detect_machine_type()
    runner = find_runner() if not own.dry_run else Path(os.environ.get("BR_RUNNER", "harness/br_run.py"))
    cmd = build_command(runner, passthrough, root, machine)
    if own.dry_run:
        print(json.dumps({"cmd": cmd, "env": SINGLE_THREAD_ENV, "machine_type": machine}, indent=1))
        return 0
    root.mkdir(parents=True, exist_ok=True)
    obs = root / "observations.jsonl"
    before = obs.read_text().splitlines() if obs.exists() else []
    rc = subprocess.call(cmd, env=single_thread_env())
    after = obs.read_text().splitlines() if obs.exists() else []
    if rc != 0 or len(after) != len(before) + 1:
        print(f"[harness] runner failed (rc={rc}); no record accepted", file=sys.stderr)
        return rc or 1
    rec = enrich(json.loads(after[-1]), machine)
    errs = validate_record(rec)
    (root / rec["logs"] / "record.json").write_text(json.dumps(rec, indent=1))
    obs.write_text("\n".join(before + [json.dumps(rec)]) + "\n")
    if errs:
        print("[harness] record failed schema validation:\n  " + "\n  ".join(errs), file=sys.stderr)
        return 2
    print(f"[harness] record {rec['id']} accepted (machine {machine['arch']}/{machine['label']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
