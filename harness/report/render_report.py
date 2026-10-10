#!/usr/bin/env python3
"""Compatibility shim. The reviewer report generator now lives in reports/ (reports/reviewer.py, entry point
`python -m reports.generate`), so the team has one report generator. This keeps Jonathan's documented command working:

    python3 harness/report/render_report.py <record.json> ... --out DIR [--root R] [--claims-dir D] [--formats md,html,pdf]

--root maps to --runs-root. --golden-dir and --observations are accepted and ignored: golden cases now come from
evals/golden_cases.json checked against evals/fixtures/golden_v1.jsonl (use --golden-records to change that).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from reports.generate import main as generate_main  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("records", nargs="+")
    ap.add_argument("--root", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--claims-dir", default=None)
    ap.add_argument("--golden-dir", default=None, help="ignored (see module docstring)")
    ap.add_argument("--observations", default=None, help="ignored (see module docstring)")
    ap.add_argument("--summary-title", default="Proof-of-Change reviewer summary")
    ap.add_argument("--formats", default="md,html,pdf")
    a = ap.parse_args(argv)
    args = [*a.records, "--out", a.out, "--formats", a.formats, "--title", a.summary_title]
    if a.root:
        args += ["--runs-root", a.root]
    if a.claims_dir:
        args += ["--claims-dir", a.claims_dir]
    return generate_main(args)


if __name__ == "__main__":
    sys.exit(main())
