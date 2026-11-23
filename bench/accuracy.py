"""False confirmations and wrong passes, counted once per pull request.

A wrong pass is the count `bench.summarize` already reports as a wrong approval: the tool stored
`verified` on a known regression. A false confirmation is a pull request the tool stored as
`verified` whose hand check says it is a real break. The hand check uses the labels already stored
on records: `break` (the expected class for a real break) and `needs_attention` (the verdict a real
break gets). No new label is added.

A pull request with several records counts once. A verified pull request with no hand check is left
out of the false-confirmation rate and counted as unchecked. Nothing here writes a record or changes
a stored verdict.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from bench.manifest import REGRESSION

VERDICT_ORDER = ("verified", "needs_attention", "could_not_verify", "no_code_change")
# Labels already used when a person or a case says the change is a real break.
REAL_BREAK = frozenset({"break", "needs_attention"})


def rate(k: int, n: int) -> dict:
    return {"count": k, "n": n, "rate": round(k / n, 4) if n else None}


def wrong_approval_rate(results: list[dict]) -> dict:
    """Same count as the benchmark summary: verified on a known regression, over those cases."""
    reg = [r for r in results if r["category"] in REGRESSION]

    def verdict(row: dict):
        return row["verdict"] if row.get("outcome") == "ran" else None

    return rate(sum(1 for row in reg if verdict(row) == "verified"), len(reg))


def shown_verdict(rec: dict) -> str:
    """Stored verdict. A missing verdict counts as could_not_verify, as the run summary already does.

    A benchmark result that did not run stays not_run, so it is not a verified result.
    """
    if "outcome" in rec and rec.get("outcome") != "ran":
        return "not_run"
    raw = rec.get("verdict")
    if not isinstance(raw, str) or not raw.strip():
        return "could_not_verify"
    return raw.strip().lower().replace(" ", "_")


def hand_mark(value) -> str | None:
    """'break' when the hand check says this is a real break, 'checked' when it says otherwise, None when absent."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return "break" if text in REAL_BREAK else "checked"
    if isinstance(value, dict):
        for key in ("expected_class", "verdict"):
            if key in value and value[key] is not None:
                marked = hand_mark(value[key])
                if marked:
                    return marked
        return "checked"
    return "checked"


def pr_key(rec: dict) -> tuple:
    """Identity of one pull request. Several records with this key count once."""
    pr = rec.get("pr")
    repo = rec.get("repo")
    number = None
    if isinstance(pr, dict):
        repo = pr.get("repo") or repo
        number = pr.get("number")
    elif isinstance(pr, int) or (isinstance(pr, str) and str(pr).isdigit()):
        number = pr
    if repo and number is not None:
        return ("pr", str(repo).lower(), str(number))
    if rec.get("case_id"):
        return ("case", str(rec["case_id"]))
    return ("source", str(rec.get("_source") or ""))


def _merged_hand(rows: list[dict]) -> str | None:
    marks = [hand_mark(r.get("hand_check")) for r in rows]
    if any(mark == "break" for mark in marks):
        return "break"
    checked = [mark for mark in marks if mark]
    return checked[-1] if checked else None


def collapse(records: list[dict]) -> list[dict]:
    """One entry per pull request. Records are grouped by pr_key; path order is only a tie break."""
    groups: dict[tuple, list[dict]] = {}
    for rec in records:
        groups.setdefault(pr_key(rec), []).append(rec)
    out = []
    for key in sorted(groups):
        rows = sorted(groups[key], key=lambda r: str(r.get("_source") or ""))
        categories = [r.get("category") for r in rows if r.get("category") in REGRESSION or r.get("category")]
        out.append({
            "key": key,
            "records": len(rows),
            "verdict": shown_verdict(rows[-1]),
            "verified": shown_verdict(rows[-1]) == "verified",
            "regression": any(r.get("category") in REGRESSION for r in rows),
            "category": categories[-1] if categories else None,
            "hand": _merged_hand(rows),
        })
    return out


def assess_saved(records: list[dict]) -> dict:
    """Rates and verdict counts for saved records. Does not write and does not change a verdict."""
    record_counts = Counter(shown_verdict(r) for r in records)
    prs = collapse(records)
    pr_counts = Counter(p["verdict"] for p in prs)
    reg = [p for p in prs if p["regression"]]
    wrong = rate(sum(1 for p in reg if p["verified"]), len(reg))
    verified = [p for p in prs if p["verified"]]
    checked = [p for p in verified if p["hand"]]
    false = [p for p in checked if p["hand"] == "break"]
    return {
        "record_verdicts": {name: record_counts.get(name, 0) for name in VERDICT_ORDER},
        "pull_request_verdicts": {name: pr_counts.get(name, 0) for name in VERDICT_ORDER},
        "records": len(records),
        "pull_requests": len(prs),
        "wrong_passes": wrong,
        "false_confirmations": rate(len(false), len(checked)),
        "unchecked": sum(1 for p in verified if not p["hand"]),
    }


def _case_id(path: Path) -> str | None:
    for part in path.parts:
        if part.startswith("bench-") and len(part) > len("bench-"):
            return part[len("bench-"):]
    return None


def records_by_case(root: Path | None) -> dict[str, list[dict]]:
    """Check records under a results folder, grouped by case. The folder is only read."""
    found: dict[str, list[dict]] = {}
    if root is None or not Path(root).is_dir():
        return found
    for path in sorted(Path(root).rglob("record.json")):
        case = _case_id(path)
        if not case:
            continue
        try:
            rec = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict):
            found.setdefault(case, []).append(rec)
    return found


def _mark_for_case(row: dict, records: list[dict]) -> str | None:
    marks = [hand_mark(row.get("hand_check"))]
    marks += [hand_mark(rec.get("hand_check")) for rec in records]
    if any(mark == "break" for mark in marks):
        return "break"
    if any(mark for mark in marks):
        return "checked"
    return None


def arm_rates(rows: list[dict], by_case: dict[str, list[dict]]) -> dict:
    """Wrong passes for this arm (the existing wrong-approval count) and false confirmations.

    Each case is one pull request. Several check records for that case still count once.
    """
    false = checked = unchecked = 0
    for row in rows:
        if row.get("outcome") != "ran" or row.get("verdict") != "verified":
            continue
        mark = _mark_for_case(row, by_case.get(row.get("case_id"), []))
        if mark is None:
            unchecked += 1
            continue
        checked += 1
        if mark == "break":
            false += 1
    return {
        "wrong_passes": wrong_approval_rate(rows),
        "false_confirmations": rate(false, checked),
        "unchecked": unchecked,
    }


def attach(root: Path, arms: dict[str, list[dict]], summary: dict) -> dict:
    """Copy of summary plus per-arm rates. The results folder is only read."""
    by_case = records_by_case(root)
    out = dict(summary)
    out["accuracy"] = {arm: arm_rates(rows, by_case) for arm, rows in arms.items()}
    return out


def _fmt(block: dict) -> str:
    if not block.get("n"):
        return "n/a (n=0)"
    return f"{block['count']}/{block['n']}"


def accuracy_paragraph(accuracy: dict) -> str:
    """Plain-language lines placed under the benchmark table."""
    lines = ["", "False confirmations, next to wrong passes. A pull request with several records counts once."]
    for arm, block in accuracy.items():
        lines.append(
            f"{arm}: wrong passes {_fmt(block['wrong_passes'])}; "
            f"false confirmations {_fmt(block['false_confirmations'])}; "
            f"unchecked verified pull requests {block['unchecked']}."
        )
    lines.append(
        "A wrong pass is a verified result on a known regression. "
        "A false confirmation is a pull request the tool called verified that the hand check says is a real break "
        "(stored label break or needs_attention). "
        "A verified pull request with no hand check is left out of that rate and counted as unchecked."
    )
    return "\n".join(lines) + "\n"


def _count_table(title: str, counts: dict, total: int) -> list[str]:
    lines = [f"## {title}", "", "| Verdict | Count |", "|---|---|"]
    for name in VERDICT_ORDER:
        lines.append(f"| {name} | {counts.get(name, 0)} |")
    lines.append(f"| total | {total} |")
    lines.append("")
    return lines


def saved_markdown(stats: dict) -> str:
    """Report text for a folder of saved records. Verdicts are copied from the records."""
    lines = ["# Saved-record report", ""]
    lines += _count_table("Verdicts, every record", stats["record_verdicts"], stats["records"])
    lines += _count_table(
        "Verdicts, one per pull request", stats["pull_request_verdicts"], stats["pull_requests"])
    lines.append(
        "Several records of one pull request count once. "
        "The pull-request table and the rates use the stored verdict on the last record in path order."
    )
    lines.append("")
    lines.append(f"Wrong passes: {_fmt(stats['wrong_passes'])}.")
    lines.append(f"False confirmations: {_fmt(stats['false_confirmations'])}.")
    lines.append(f"Unchecked verified pull requests: {stats['unchecked']}.")
    lines.append("")
    lines.append(
        "A wrong pass is a verified result on a known regression. "
        "A false confirmation is a pull request the tool called verified that the hand check says is a real break "
        "(stored label break or needs_attention). "
        "A verified pull request with no hand check is left out of that rate and counted as unchecked."
    )
    lines.append("")
    return "\n".join(lines)


def read_saved(root: Path) -> list[dict]:
    """Every record.json under root. Unreadable files are skipped. Nothing is written."""
    records = []
    for path in sorted(Path(root).rglob("record.json")):
        try:
            rec = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict):
            item = dict(rec)
            item["_source"] = path.as_posix()
            records.append(item)
    return records


def saved_report(root: Path) -> str:
    return saved_markdown(assess_saved(read_saved(root)))
