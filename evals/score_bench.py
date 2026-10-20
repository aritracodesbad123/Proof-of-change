"""Benchmark scorer (stdlib only): joins result files with an answer key ON A CASE ID ONLY and reports recall,
false-alarm rate and abstention with Wilson 95% intervals, plus an exact McNemar test for two systems on the same
cases.

Generic: any answer-key CSV with an ID column (default `id`, `--id-column`) and a label column (default `label`,
`--label-column`); any case IDs (B01, R-numpy-2.3, ...). It is the ONLY module that reads an answer key. Nothing it
reads from the key is passed back to a generator: it prints aggregate numbers and per-ID outcomes only.

Result files: one JSON per case and baseline (benchmark mode, `ops/daily_run.py --bench`, or any other mode that
writes the same fields). A result counts by its case ID, taken from the first of `bench.id`, `case.id`, `case_id`
that is set (never from repo or PR fields), and by its `verdict`:

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
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
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


def read_answers(path: str | Path, id_column: str = "id", label_column: str = "label") -> dict[str, str]:
    """{case id: 'pos' | 'neg'} from an answer key. Only the ID and label columns are used."""
    out = {}
    with open(path, newline="") as fh:
        rd = csv.DictReader(fh)
        missing = [c for c in (id_column, label_column) if c not in (rd.fieldnames or [])]
        if missing:
            raise ValueError(f"{Path(path).name}: no column(s) {', '.join(missing)}")
        for row in rd:
            rid, label = (row.get(id_column) or "").strip(), (row.get(label_column) or "").strip().lower()
            if not ID_RE.match(rid):
                continue
            if label.startswith("regression"):
                out[rid] = "pos"
            elif label.startswith(("safe", "negative")):
                out[rid] = "neg"
    return out


def result_id(rec: dict) -> str | None:
    """The case ID of a result: bench.id, case.id or case_id (the record's own `id` is a run id, not a case id)."""
    rid = (rec.get("bench") or {}).get("id") or (rec.get("case") or {}).get("id") or rec.get("case_id")
    return rid if isinstance(rid, str) and ID_RE.match(rid) else None


# A study record must carry each of these, and none of them may be true.
# swarm and operator_approval are on/off (on counts as true). The requested fields are booleans.
STUDY_SWITCHES = (
    "swarm_requested",
    "operator_approval_requested",
    "swarm",
    "operator_approval",
)


def _call_count(value) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def invalid_record_problems(name: str, rec: dict) -> list[str]:
    """Why this result must not be scored. Empty when the record is a usable model run.

    A record marked invalid, a record whose model_provider_used is exactly none, or a record whose
    AI calls all failed must not be counted as could_not_verify. A record that simply omits
    model_provider_used is left alone, so an older fixture still scores.
    """
    problems = []
    if rec.get("invalid") is True:
        why = rec.get("invalid_reason")
        detail = f" ({why})" if isinstance(why, str) and why else ""
        problems.append(f"{name}: invalid{detail}; it must not be counted as could_not_verify")
    if rec.get("model_provider_used") == "none":
        problems.append(f"{name}: model_provider_used is none; it must not be counted as could_not_verify")
    cost = rec.get("cost")
    if isinstance(cost, dict):
        ai = _call_count(cost.get("ai_calls"))
        failed = _call_count(cost.get("failed_ai_calls"))
        swarm = cost.get("swarm")
        if isinstance(swarm, dict):
            ai += _call_count(swarm.get("ai_calls"))
            failed += _call_count(swarm.get("failed_ai_calls"))
        if ai > 0 and failed >= ai:
            problems.append(f"{name}: every AI call failed; it must not be counted as could_not_verify")
    return problems


def study_record_problems(name: str, rec: dict) -> list[str]:
    """Why this result cannot be scored as a study record. Empty when all four switches are off.

    A true value, or a missing value, is not a study record. ``on`` counts as true.
    Anything other than an explicit false or ``off`` counts as missing.
    An invalid model record is refused as well, so it is not counted as could_not_verify.
    """
    problems = []
    for key in STUDY_SWITCHES:
        if key not in rec:
            problems.append(f"{name}: {key} is missing")
            continue
        value = rec[key]
        if value is True or value == "on":
            problems.append(f"{name}: {key} is true")
        elif value is False or value == "off":
            continue
        else:
            problems.append(f"{name}: {key} is missing")
    problems.extend(invalid_record_problems(name, rec))
    return problems


def study_records_message(records: list[tuple[str, dict]]) -> str | None:
    """Plain refusal when any study record has one of the four switches true or missing, or is invalid."""
    problems = [p for name, rec in records for p in study_record_problems(name, rec)]
    if not problems:
        return None
    return (
        "STOPPED: these results cannot be scored as a study. "
        "Every study record must include swarm_requested, operator_approval_requested, "
        "swarm, and operator_approval, and none of them may be true. "
        "On counts as true. A missing value is not a study record. "
        "A record whose AI calls all failed, whose model_provider_used is none, "
        "or that is marked invalid is refused and is not counted as could_not_verify.\n"
        + "\n".join(problems)
    )


def result_records(folder: str | Path) -> list[tuple[str, dict]]:
    """Result files the scorer would use: (file name, record). Skips answer-key names and non-results."""
    found = []
    for f in sorted(Path(folder).glob("*.json")):
        if "answers" in f.name.lower():
            continue
        try:
            rec = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict) and result_id(rec):
            found.append((f.name, rec))
    return found


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
    ap.add_argument("--answers", required=True, help="an answer-key CSV (ID and label columns); read by this scorer only")
    ap.add_argument("--id-column", default="id", help="answer-key column holding the case ID (default: id)")
    ap.add_argument("--label-column", default="label", help="answer-key column holding the label (default: label)")
    ap.add_argument("--results", required=True, help="folder of result JSON files (one per case and baseline)")
    ap.add_argument("--baseline", default=None, help="score only results of this baseline")
    ap.add_argument("--vs", default=None, help="second baseline in the same folder: paired exact McNemar test")
    ap.add_argument("--json", default=None, help="also write the numbers to this JSON file")
    a = ap.parse_args(argv)
    refusal = study_records_message(result_records(a.results))
    if refusal:
        print(refusal, file=sys.stderr)
        return 1
    answers = read_answers(a.answers, a.id_column, a.label_column)
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
