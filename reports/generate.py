"""Reviewer reports for the human approver: the single report generator for Blast Radius / Proof-of-Change.

    python -m reports.generate INPUT [INPUT ...] --out reports/daily/2026-10-11 \
        [--runs-root /workspace/blast-radius-research] [--claims-dir DIR] [--formats md,html,pdf] [--require-v1]

INPUT is any mix of:
  * a record.json (its own directory is used as the run directory when --runs-root does not resolve it),
  * an observations .jsonl (one record per line),
  * an eval result .json from `python -m evals.run_evals --out` (the records embedded in it).

Output: <out>/<run id>/REPORT.md|html|pdf for every record, and <out>/SUMMARY.md|html|pdf (the daily summary,
needs-attention items first). Report content and rules: docs/REPORT_SPEC.md; code: reports/reviewer.py (ported
from Jonathan's harness/report/render_report.py, which is now a thin shim to this module).
Exit code: 0 on success, 2 if a PDF was requested but could not be rendered.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from reports import reviewer


def load_inputs(paths: list[str]) -> list[tuple[dict, Path | None]]:
    """-> [(record, record_path or None)]"""
    out: list[tuple[dict, Path | None]] = []
    for p in map(Path, paths):
        if p.suffix == ".jsonl":
            out += [(json.loads(x), None) for x in p.read_text().splitlines() if x.strip()]
            continue
        data = json.loads(p.read_text())
        if isinstance(data, dict) and isinstance(data.get("records"), list):  # eval result
            out += [(e["record"], None) for e in data["records"]]
        else:
            out.append((data, p))
    return out


def generate(paths: list[str], out: str | Path, runs_root: str | Path | None = None, claims_dir: str | Path | None = None,
             formats=("md", "html", "pdf"), title: str = "Proof-of-Change reviewer summary", require_v1: bool | None = None,
             golden_records: str | Path | None = None) -> list[dict]:
    out = Path(out)
    golden = reviewer.golden_status(reviewer.load_records_file(golden_records or reviewer.GOLDEN_RECORDS))
    sums = []
    for rec, rpath in load_inputs(paths):
        cp = Path(claims_dir) / f"{rec['id']}.claims.json" if claims_dir else None
        sums.append(reviewer.render_record(rec, str(out / rec["id"]), runs_root, rpath, cp, golden, formats, require_v1))
    sums_err = reviewer.write_summary(sums, str(out), title, formats)
    for s in sums:
        s["summary_pdf_error"] = sums_err
    return reviewer.sort_summaries(sums)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="record.json, observations .jsonl, or eval-results .json")
    ap.add_argument("-o", "--out", required=True, help="output dir: one subdir per run id plus SUMMARY.* (-o is an alias)")
    ap.add_argument("--runs-root", default=None, help="directory that record['logs'] paths are relative to")
    ap.add_argument("--claims-dir", default=None, help="dir with <run id>.claims.json files (else the record's `claims` field)")
    ap.add_argument("--golden-records", default=None, help=f"stored golden records (default {reviewer.GOLDEN_RECORDS})")
    ap.add_argument("--formats", default="md,html,pdf")
    ap.add_argument("--title", default="Proof-of-Change reviewer summary")
    ap.add_argument("--require-v1", action="store_true", help="evals validate against the full shared v1 schema")
    a = ap.parse_args(argv)
    formats = tuple(f.strip() for f in a.formats.split(",") if f.strip())
    sums = generate(a.inputs, a.out, a.runs_root, a.claims_dir, formats, a.title, True if a.require_v1 else None, a.golden_records)
    rc = 0
    for s in sums:
        print(f"{s['id']}: {s['verdict']} | {s['action']} | confidence {s['confidence']} | evals {s['evals']} | "
              f"citations {s['citations']}" + (f" | PDF: {s['pdf_error']}" if s["pdf_error"] else ""))
        rc = 2 if s["pdf_error"] else rc
    err = sums[0]["summary_pdf_error"] if sums else None
    print("summary:", Path(a.out) / "SUMMARY.html", err or "")
    return 2 if err else rc


if __name__ == "__main__":
    sys.exit(main())
