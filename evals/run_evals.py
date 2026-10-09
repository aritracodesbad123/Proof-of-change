"""Run all evals over an observations file and write a JSON result.

    python -m evals.run_evals --observations data/observations.jsonl --runs-root data --out eval-results.json

Exit code 1 if any check fails (CI gate), 0 otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evals.checks import evaluate_record, golden_coverage, load_golden, recommendation
from harness.machine import detect_machine_type


def run(observations: Path, runs_root: Path | None, require_ci_fields: bool, golden: Path | None = None,
        require_golden: bool = False) -> dict:
    cases = load_golden(golden) if golden else load_golden()
    records = [json.loads(line) for line in Path(observations).read_text().splitlines() if line.strip()]
    per_record = []
    all_results = []
    for rec in records:
        res = evaluate_record(rec, runs_root, cases, require_ci_fields)
        all_results += res
        per_record.append({"id": rec.get("id"), "record": rec, "results": [r.to_dict() for r in res],
                           "recommendation": recommendation(res)})
    cov = golden_coverage(records, cases, require_golden)
    all_results += cov
    counts: dict[str, int] = {}
    for r in all_results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return {"observations": str(observations), "evaluator_machine_type": detect_machine_type(),
            "require_ci_fields": require_ci_fields, "records": per_record,
            "golden_coverage": [r.to_dict() for r in cov], "counts": counts,
            "recommendation": recommendation(all_results)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--observations", required=True)
    ap.add_argument("--runs-root", default=None, help="directory that record['logs'] paths are relative to")
    ap.add_argument("--golden", default=None)
    ap.add_argument("--legacy", action="store_true", help="do not require machine_type/thread_env (pre-harness records)")
    ap.add_argument("--require-golden", action="store_true", help="golden batch: every active golden case must be present")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    out = run(Path(a.observations), Path(a.runs_root) if a.runs_root else None, not a.legacy,
              Path(a.golden) if a.golden else None, a.require_golden)
    txt = json.dumps(out, indent=1)
    if a.out:
        Path(a.out).write_text(txt)
    print(json.dumps({"counts": out["counts"], "recommendation": out["recommendation"]}))
    return 1 if out["recommendation"] == "REJECT" else 0


if __name__ == "__main__":
    sys.exit(main())
