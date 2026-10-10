"""Run all evals over an observations file and write a JSON result.

    python -m evals.run_evals --observations data/observations.jsonl --runs-root data --out eval-results.json
    python -m evals.run_evals --observations evals/fixtures/golden_v1.jsonl --require-golden --require-v1   # golden batch

Exit code 1 if any check fails (CI gate), 0 otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evals.checks import GOLDEN_PR_BATCH, evaluate_record, golden_coverage, load_golden, recommendation
from harness.machine import detect_machine_type


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def run(observations: Path, runs_root: Path | None, require_ci_fields: bool, golden: Path | None = None,
        require_golden: bool = False, require_v1: bool | None = None, pr_observations: Path | None = None) -> dict:
    """pr_observations: known-answer PR runs (record_kind pr_run). A golden batch (require_golden) always includes the
    golden PR batch (evals/fixtures/golden_pr_v1.jsonl) unless another file is given."""
    cases = load_golden(golden) if golden else load_golden()
    records = load(observations)
    if pr_observations is None and require_golden and GOLDEN_PR_BATCH.exists():
        pr_observations = GOLDEN_PR_BATCH
    pr_records = load(pr_observations) if pr_observations else []
    per_record = []
    all_results = []
    for rec in records:
        res = evaluate_record(rec, runs_root, cases, require_ci_fields, require_v1)
        all_results += res
        per_record.append({"id": rec.get("id"), "record": rec, "results": [r.to_dict() for r in res],
                           "recommendation": recommendation(res)})
    per_pr = []
    for rec in pr_records:
        res = evaluate_record(rec, None, cases, True, require_v1)
        all_results += res
        per_pr.append({"id": rec.get("id"), "results": [r.to_dict() for r in res], "recommendation": recommendation(res)})
    cov = golden_coverage(records + pr_records, cases, require_golden)
    all_results += cov
    counts: dict[str, int] = {}
    for r in all_results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return {"observations": str(observations), "evaluator_machine_type": detect_machine_type(),
            "require_ci_fields": require_ci_fields, "require_v1": bool(require_v1), "records": per_record,
            "pr_observations": str(pr_observations) if pr_observations else None, "pr_records": per_pr,
            "golden_coverage": [r.to_dict() for r in cov], "counts": counts,
            "recommendation": recommendation(all_results)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--observations", required=True)
    ap.add_argument("--runs-root", default=None, help="directory that record['logs'] paths are relative to")
    ap.add_argument("--golden", default=None)
    ap.add_argument("--legacy", action="store_true", help="do not require machine_type/thread_env (pre-harness records)")
    ap.add_argument("--require-golden", action="store_true", help="golden batch: every active golden case must be present")
    ap.add_argument("--require-v1", action="store_true",
                    help="validate every record against the full shared v1 schema (golden batches)")
    ap.add_argument("--pr-observations", default=None,
                    help="known-answer PR runs (record_kind pr_run); default with --require-golden: "
                         "evals/fixtures/golden_pr_v1.jsonl")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    out = run(Path(a.observations), Path(a.runs_root) if a.runs_root else None, not a.legacy,
              Path(a.golden) if a.golden else None, a.require_golden, True if a.require_v1 else None,
              Path(a.pr_observations) if a.pr_observations else None)
    txt = json.dumps(out, indent=1)
    if a.out:
        Path(a.out).write_text(txt)
    print(json.dumps({"counts": out["counts"], "recommendation": out["recommendation"]}))
    return 1 if out["recommendation"] == "REJECT" else 0


if __name__ == "__main__":
    sys.exit(main())
