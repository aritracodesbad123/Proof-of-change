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

from evals.pr_metrics import LABELS_PATH, blind_score, case_for, load_cases, non_blind_probes, record_is_blind, score, score_records
from poc import model_provider

BASELINES = ("tests", "tests+diff", "tests+probes", "full")
REPO_ROOT = Path(__file__).resolve().parent.parent


def load_records(root: Path) -> list[dict]:
    files = sorted(root.rglob("records.jsonl"))
    if files:
        return [json.loads(ln) for f in files for ln in f.read_text().splitlines() if ln.strip()]
    return [json.loads(f.read_text()) for f in sorted(root.rglob("record.json"))]


def _rate(n: int, d: int) -> str:
    return f"{n}/{d}" if d else "n/a"


def _metrics(cases: list[dict], recs: list[dict], blind: bool) -> dict:
    """Rates over the labelled cases that HAVE a verdict here (a case without a record is not a miss)."""
    v = {c["id"]: r["verdict"] for r in recs if (c := case_for(cases, r))}
    matched = [c for c in cases if c["id"] in v]
    s = blind_score(matched, [r for r in recs if case_for(cases, r)]) if blind else score(matched, v)
    return {"records": len(recs), "labelled": len(v), "unlabelled": len(recs) - len(v),
            "catch": _rate(len(s["caught"]), s["scored_regressions"]),
            "false_alarms": _rate(len(s["false_alarms"]), s["scored_safe"]),
            "could_not_verify": _rate(len(s["could_not_verify"]), len(v)), "detail": s}


def row(baseline: str, cases: list[dict], records: list[dict]) -> dict:
    blind = [r for r in records if record_is_blind(r)]
    other = [r for r in records if not record_is_blind(r)]
    nb = _metrics(cases, other, False)
    nb["label"] = score_records(cases, other)["not_blind"]["label"]
    nb["why"] = {r.get("id"): non_blind_probes(r) for r in other}
    return {"baseline": baseline, "records": len(records), "blind": _metrics(cases, blind, True), "not_blind": nb}


def table(rows: list[dict]) -> str:
    out = ["| Baseline | Records (labelled) | Catch (blind) | False alarms (blind) | Could not verify (blind) | "
           "NOT BLIND: records (labelled), catch, false alarms, could not verify |", "|---|---|---|---|---|---|"]
    for r in rows:
        b, nb = r["blind"], r["not_blind"]
        out.append(f"| {r['baseline']} | {r['records']} ({b['labelled'] + nb['labelled']}) | {b['catch']} | "
                   f"{b['false_alarms']} | {b['could_not_verify']} | {nb['records']} ({nb['labelled']}), {nb['catch']}, "
                   f"{nb['false_alarms']}, {nb['could_not_verify']} |")
    out += ["", "Blind columns count only verdicts that no non-blind probe could decide (live model probes that "
            "passed the freeze rule, or no deciding probe). The NOT BLIND column covers post-hoc fixed probes, "
            "recorded model fixtures and differential probes: known-answer data, not blind results. Catch = "
            "needs_attention on a caused_regression case; false alarm = needs_attention on a safe case; could not "
            "verify is never counted as a catch. Rates use only labelled cases that have a record; unlabelled records "
            "are counted but not scored."]
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
        stop = model_provider.key_refusal(a.model_provider)
        if stop:
            print(stop, file=sys.stderr)
            return 1
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
