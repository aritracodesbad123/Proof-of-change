"""Score a swarm-on study folder.

Swarm-on benchmark results are written to their own folder, the main folder name plus
``-swarm-on``. This scorer reads that folder. It accepts a record only when the swarm
was requested and the swarm step ran, and when operator approval was not requested and
did not run. The main study scorer does not read this folder, and it still refuses a
swarm-on record that is placed in the main folder.

    python -m evals.score_swarm --answers <answers.csv> --results runs/bench-v0-swarm-on
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evals.score_bench import compare, read_answers, read_results, result_records, score, table


def swarm_record_problems(name: str, rec: dict) -> list[str]:
    """Why this result cannot be scored as a swarm study. Empty only when the swarm was requested and ran.

    Operator approval must still be explicitly off. A missing swarm field is not a swarm study record.
    """
    problems = []
    if "swarm_requested" not in rec:
        problems.append(f"{name}: swarm_requested is missing")
    elif rec["swarm_requested"] is not True:
        problems.append(f"{name}: swarm_requested is not set")
    if "swarm" not in rec:
        problems.append(f"{name}: swarm is missing")
    elif rec["swarm"] != "on":
        problems.append(f"{name}: the advisory swarm did not run")
    for key in ("operator_approval_requested", "operator_approval"):
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
    return problems


def swarm_records_message(records: list[tuple[str, dict]]) -> str | None:
    """Plain refusal unless every record has the swarm requested and run."""
    problems = [p for name, rec in records for p in swarm_record_problems(name, rec)]
    if not problems:
        return None
    return (
        "STOPPED: these results cannot be scored as a swarm study. "
        "Every record must have the advisory swarm requested and run, "
        "and operator approval must stay off.\n"
        + "\n".join(problems)
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--answers", required=True, help="an answer-key CSV (ID and label columns); read by this scorer only")
    ap.add_argument("--id-column", default="id", help="answer-key column holding the case ID (default: id)")
    ap.add_argument("--label-column", default="label", help="answer-key column holding the label (default: label)")
    ap.add_argument("--results", required=True, help="swarm-on result folder (name ends with -swarm-on)")
    ap.add_argument("--baseline", default=None, help="score only results of this baseline")
    ap.add_argument("--vs", default=None, help="second baseline in the same folder: paired exact McNemar test")
    ap.add_argument("--json", default=None, help="also write the numbers to this JSON file")
    a = ap.parse_args(argv)
    refusal = swarm_records_message(result_records(a.results))
    if refusal:
        print(refusal, file=sys.stderr)
        return 1
    answers = read_answers(a.answers, a.id_column, a.label_column)
    res = read_results(a.results, a.baseline)
    s = score(answers, res)
    out = {"baseline": a.baseline, "score": s, "kind": "swarm"}
    print(table(f"swarm baseline {a.baseline or '(all)'}", s))
    if a.vs:
        other = read_results(a.results, a.vs)
        out["vs"] = {"baseline": a.vs, "score": score(answers, other), "paired": compare(answers, res, other)}
        p = out["vs"]["paired"]
        print("\n" + table(f"swarm baseline {a.vs}", out["vs"]["score"]))
        print(f"\nPaired on {p['paired_regressions']} regression(s): flagged only by {a.baseline}: "
              f"{len(p['only_a_flagged'])}, only by {a.vs}: {len(p['only_b_flagged'])}; exact McNemar two-sided "
              f"p = {p['mcnemar_exact_p_two_sided']:.3f}")
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
