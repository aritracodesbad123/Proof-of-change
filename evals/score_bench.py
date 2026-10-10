"""Benchmark scorer (stdlib only): joins result files with the answer key ON ID ONLY and reports recall, false-alarm
rate and abstention with Wilson 95% intervals, plus an exact McNemar test for two systems on the same cases.

This is the ONLY module that reads the answer key (`*answers*.csv`, columns id,label,...). Nothing it reads from the
answer key is passed back to a generator: it prints aggregate numbers and per-ID outcomes only.

Result files: one JSON per case and baseline, as written by benchmark mode (`ops/daily_run.py --bench`). A result
counts by its `bench.id` (falling back to an `id` field of the form B01) and its `verdict`:

    needs_attention   -> flagged
    verified          -> not flagged
    could_not_verify  -> abstained (counted as not flagged for recall and false alarms, and reported separately)

Labels: a label starting with "regression" is a positive, one starting with "safe" (or "negative") is a negative.

    python -m evals.score_bench --answers <answers.csv> --results runs/bench-v0 [--baseline full]
    python -m evals.score_bench --answers <answers.csv> --results runs/bench-v0 --baseline full --vs tests
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

Z95 = 1.959963984540054
ID_RE = re.compile(r"^B\d{2,}$")
FLAGGED, CLEAN, ABSTAIN = "needs_attention", "verified", "could_not_verify"


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for k successes out of n (95% by default). n = 0 gives (0, 1)."""
    if n <= 0:
        return 0.0, 1.0
    if not 0 <= k <= n:
        raise ValueError(f"k={k} must be between 0 and n={n}")
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, mid - half), min(1.0, mid + half)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from the discordant counts b (A right, B wrong) and c (A wrong, B right):
    a two-sided binomial test of min(b, c) out of b + c at p = 0.5. No discordant pairs gives 1.0."""
    if b < 0 or c < 0:
        raise ValueError("discordant counts must be >= 0")
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def read_answers(path: str | Path) -> dict[str, str]:
    """{id: 'pos' | 'neg'} from the answer key. Only the id and label columns are used."""
    out = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            rid, label = (row.get("id") or "").strip(), (row.get("label") or "").strip().lower()
            if not ID_RE.match(rid):
                continue
            if label.startswith("regression"):
                out[rid] = "pos"
            elif label.startswith(("safe", "negative")):
                out[rid] = "neg"
    return out


def result_id(rec: dict) -> str | None:
    rid = (rec.get("bench") or {}).get("id") or rec.get("id")
    return rid if isinstance(rid, str) and ID_RE.match(rid) else None


def read_results(folder: str | Path, baseline: str | None = None) -> dict[str, str]:
    """{id: verdict} from the result JSON files in folder (not recursive). With baseline, only results of that
    baseline (records without one count as 'full'). Two results for one ID and baseline is an error."""
    out: dict[str, str] = {}
    for f in sorted(Path(folder).glob("*.json")):
        if "answers" in f.name.lower():
            continue
        try:
            rec = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        rid = result_id(rec) if isinstance(rec, dict) else None
        if rid is None:
            continue
        if baseline and (rec.get("baseline") or "full") != baseline:
            continue
        if rid in out:
            raise ValueError(f"two results for {rid}" + (f" (baseline {baseline})" if baseline else "")
                             + "; pass --baseline")
        out[rid] = rec.get("verdict") or ABSTAIN
    return out


def score(answers: dict[str, str], results: dict[str, str]) -> dict:
    """Metrics over the IDs present in both (joined on ID only). Missing results are listed, not guessed."""
    ids = sorted(set(answers) & set(results))
    pos = [i for i in ids if answers[i] == "pos"]
    neg = [i for i in ids if answers[i] == "neg"]
    flagged = {i for i in ids if results[i] == FLAGGED}
    abstained = {i for i in ids if results[i] == ABSTAIN}

    def block(k: int, n: int) -> dict:
        lo, hi = wilson(k, n)
        return {"k": k, "n": n, "rate": (k / n) if n else None, "ci95": [lo, hi]}

    return {"cases_scored": len(ids), "missing_results": sorted(set(answers) - set(results)),
            "unknown_ids": sorted(set(results) - set(answers)),
            "regression_recall": block(len(flagged & set(pos)), len(pos)),
            "false_alarm_rate": block(len(flagged & set(neg)), len(neg)),
            "abstention_rate": block(len(abstained), len(ids)),
            "precision_of_flags": block(len(flagged & set(pos)), len(flagged)),
            "per_id": {i: {"label": answers[i], "verdict": results[i]} for i in ids}}


def compare(answers: dict[str, str], a: dict[str, str], b: dict[str, str]) -> dict:
    """Paired comparison on the regression cases both systems ran: correct = flagged. Exact McNemar."""
    ids = sorted(i for i in set(a) & set(b) if answers.get(i) == "pos")
    only_a = [i for i in ids if a[i] == FLAGGED and b[i] != FLAGGED]
    only_b = [i for i in ids if b[i] == FLAGGED and a[i] != FLAGGED]
    return {"paired_regressions": len(ids), "only_a_flagged": only_a, "only_b_flagged": only_b,
            "mcnemar_exact_p_two_sided": mcnemar_exact(len(only_a), len(only_b))}


def table(name: str, s: dict) -> str:
    rows = [("Regression recall", s["regression_recall"]), ("False-alarm rate", s["false_alarm_rate"]),
            ("Abstention (could not verify)", s["abstention_rate"]), ("Precision of flags", s["precision_of_flags"])]
    out = [f"### {name}", "", "| Metric | k / n | Rate | Wilson 95% CI |", "|---|---|---|---|"]
    for label, m in rows:
        rate = pct(m["rate"]) if m["rate"] is not None else "n/a"
        out.append(f"| {label} | {m['k']} / {m['n']} | {rate} | {pct(m['ci95'][0])} to {pct(m['ci95'][1])} |")
    if s["missing_results"]:
        out.append(f"\nNo result yet for: {', '.join(s['missing_results'])} (not counted).")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--answers", required=True, help="the answer key CSV (id,label,...); read by this scorer only")
    ap.add_argument("--results", required=True, help="folder of result JSON files (one per case and baseline)")
    ap.add_argument("--baseline", default=None, help="score only results of this baseline")
    ap.add_argument("--vs", default=None, help="second baseline in the same folder: paired exact McNemar test")
    ap.add_argument("--json", default=None, help="also write the numbers to this JSON file")
    a = ap.parse_args(argv)
    answers = read_answers(a.answers)
    res = read_results(a.results, a.baseline)
    s = score(answers, res)
    out = {"baseline": a.baseline, "score": s}
    print(table(f"baseline {a.baseline or '(all)'}", s))
    if a.vs:
        other = read_results(a.results, a.vs)
        out["vs"] = {"baseline": a.vs, "score": score(answers, other), "paired": compare(answers, res, other)}
        p = out["vs"]["paired"]
        print("\n" + table(f"baseline {a.vs}", out["vs"]["score"]))
        print(f"\nPaired on {p['paired_regressions']} regression(s): flagged only by {a.baseline}: "
              f"{len(p['only_a_flagged'])}, only by {a.vs}: {len(p['only_b_flagged'])}; exact McNemar two-sided "
              f"p = {p['mcnemar_exact_p_two_sided']:.3f}")
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
