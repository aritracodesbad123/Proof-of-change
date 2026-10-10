"""Ablation: a labelled PR set under each baseline (tests, tests+diff, tests+probes, full), one table.

    python -m evals.ablation --records-root DIR [--labels evals/labelled_prs.json] [--out OUT]
    python -m evals.ablation --run --out-dir DIR [--model-provider recorded] [--case ID ...]   # runs, then scores

Scoring mode reads every record under DIR/<baseline>/ (records.jsonl files, else record.json files) and matches
records to labelled cases by repo and PR number. Run mode first runs each case under each baseline with
ops/daily_run.py (--pr <url> --baseline <b> --ops-dir DIR/<b> --no-report), sandboxed like every run.

Per baseline (evals/pr_metrics.py):
  BLIND columns      catch rate, false alarms, could-not-verify rate, over records whose verdict no non-blind
                     probe could decide (only live model probes that passed the freeze rule are blind);
  NOT BLIND column   the same counts over the other records (post-hoc fixed probes, recorded model fixtures,
                     differential probes), labelled and never mixed into the blind metrics.
Writes ablation.md and ablation.json (to --out, default the records root). Small sets: read counts, not rates.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from evals.pr_metrics import LABELS_PATH, load_cases, score_records

BASELINES = ("tests", "tests+diff", "tests+probes", "full")
REPO_ROOT = Path(__file__).resolve().parent.parent


def load_records(root: Path) -> list[dict]:
    files = sorted(root.rglob("records.jsonl"))
    if files:
        return [json.loads(ln) for f in files for ln in f.read_text().splitlines() if ln.strip()]
    return [json.loads(f.read_text()) for f in sorted(root.rglob("record.json"))]


def _rate(n: int, d: int) -> str:
    return f"{n}/{d}" if d else "n/a"


def row(baseline: str, cases: list[dict], records: list[dict]) -> dict:
    s = score_records(cases, records)
    b, nb = s["blind"], s["not_blind"]
    scored_b = [r for r in records if r.get("id") not in nb["records"]]
    cnv_b = len(b["could_not_verify"])
    return {"baseline": baseline, "records": len(records),
            "blind": {"catch": _rate(len(b["caught"]), b["scored_regressions"]),
                      "false_alarms": _rate(len(b["false_alarms"]), b["scored_safe"]),
                      "could_not_verify": _rate(cnv_b, len(scored_b)), "detail": b},
            "not_blind": {"records": len(nb["records"]),
                          "catch": _rate(len(nb["caught"]), nb["scored_regressions"] if nb["records"] else 0),
                          "false_alarms": _rate(len(nb["false_alarms"]), nb["scored_safe"] if nb["records"] else 0),
                          "could_not_verify": _rate(len(nb["could_not_verify"]), len(nb["records"])),
                          "label": nb["label"], "detail": nb}}


def table(rows: list[dict]) -> str:
    out = ["| Baseline | Records | Catch (blind) | False alarms (blind) | Could not verify (blind) | "
           "NOT BLIND: records, catch, false alarms, could not verify |", "|---|---|---|---|---|---|"]
    for r in rows:
        nb = r["not_blind"]
        out.append(f"| {r['baseline']} | {r['records']} | {r['blind']['catch']} | {r['blind']['false_alarms']} | "
                   f"{r['blind']['could_not_verify']} | {nb['records']}, {nb['catch']}, {nb['false_alarms']}, "
                   f"{nb['could_not_verify']} |")
    out += ["", "Blind columns count only verdicts that no non-blind probe could decide (live model probes that "
            "passed the freeze rule, or no deciding probe). The NOT BLIND column covers post-hoc fixed probes, "
            "recorded model fixtures and differential probes: known-answer data, not blind results. Catch = "
            "needs_attention on a caused_regression case; false alarm = needs_attention on a safe case; could not "
            "verify is never counted as a catch."]
    return "\n".join(out) + "\n"


def run_cases(cases: list[dict], out_dir: Path, provider: str, baselines=BASELINES) -> None:
    for b in baselines:
        for c in cases:
            url = f"https://github.com/{c['input']['repo']}/pull/{c['input']['pr']}"
            subprocess.run([sys.executable, str(REPO_ROOT / "ops" / "daily_run.py"), "--pr", url, "--baseline", b,
                            "--ops-dir", str(out_dir / b), "--no-report", "--model-provider", provider], check=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", default=str(LABELS_PATH))
    ap.add_argument("--records-root", default=None, help="DIR with one sub-folder per baseline")
    ap.add_argument("--run", action="store_true", help="run every case under every baseline first (slow)")
    ap.add_argument("--out-dir", default=None, help="with --run: where the runs go (becomes the records root)")
    ap.add_argument("--model-provider", default="none", choices=("nebius", "recorded", "none"))
    ap.add_argument("--case", action="append", default=[], help="limit to these case ids")
    ap.add_argument("--out", default=None, help="folder for ablation.md / ablation.json (default: records root)")
    a = ap.parse_args(argv)
    cases = [c for c in load_cases(Path(a.labels)) if not a.case or c["id"] in a.case]
    root = Path(a.out_dir or a.records_root or "")
    if not str(root):
        ap.error("give --records-root, or --run with --out-dir")
    if a.run:
        run_cases([c for c in cases if c["input"].get("repo") not in (None, "TODO")], root, a.model_provider)
    rows = [row(b, cases, load_records(root / b)) for b in BASELINES if (root / b).is_dir()]
    out = Path(a.out or root)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ablation.json").write_text(json.dumps({"labels": a.labels, "rows": rows}, indent=1))
    (out / "ablation.md").write_text("# Ablation by baseline\n\n" + table(rows))
    print(table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
