"""False confirmations and wrong passes from data/hand_checks.jsonl.

Hand checks are read only from that file in this repository. A row applies to a saved record
only when the repository, pull request number, and head commit all match. A record at another
head stays unlabelled. Every verified record of a pull request is checked, not only the latest.
A label for one head is not applied to a record at another head.

A wrong pass is a verified pull request whose matching row says it really breaks something
(`broken` true). The false-confirmation rate is those pull requests over the verified pull
requests that have a matching row. Unlabelled verified pull requests are counted on their own
and are not treated as passes. Several records of one pull request at the same head count once.

`tool_verdict` and `score` are notes. They do not change the rate. Nothing here writes a record
or changes a stored verdict. A missing file is reported as not available. A malformed row fails.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from bench.manifest import REGRESSION

VERDICT_ORDER = ("verified", "needs_attention", "could_not_verify", "no_code_change")
CHECKER_VERDICTS = frozenset({"verified", "needs_attention", "could_not_verify"})
FIELDS = (
    "repo", "pr", "head", "base", "date", "checker_verdict", "checker_note", "broken",
    "tool_verdict", "score", "poc_commit", "source", "also_checked",
)
SHA = re.compile(r"^[0-9a-f]{40}$")
POC_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
REPO = re.compile(r"^[^/\s]+/[^/\s]+$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SCORES = frozenset({"agree", "false_alarm", "miss", "settled_abstention", "other"})
DEFAULT_HAND_CHECKS = Path(__file__).resolve().parents[1] / "data" / "hand_checks.jsonl"


class HandCheckError(ValueError):
    """A hand-check row is missing, mistyped, or repeated."""


def rate(k: int, n: int) -> dict:
    return {"count": k, "n": n, "rate": round(k / n, 4) if n else None}


def wrong_approval_rate(results: list[dict]) -> dict:
    """Verified results on a known regression, over those cases. The benchmark table uses this."""
    reg = [row for row in results if row["category"] in REGRESSION]

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


def record_identity(rec: dict) -> tuple[str | None, int | None, str | None]:
    """Repository, pull request number, and the head commit stored on the record. Nothing is guessed."""
    pr = rec.get("pr") if isinstance(rec.get("pr"), dict) else {}
    repo = pr.get("repo") if isinstance(pr.get("repo"), str) and pr.get("repo") else None
    if repo is None and isinstance(rec.get("repo"), str) and rec.get("repo"):
        repo = rec["repo"]
    number = pr.get("number") if isinstance(pr, dict) else None
    if type(number) is not int:
        raw_pr = rec.get("pr")
        number = raw_pr if type(raw_pr) is int else None
    head = pr.get("head_sha") if isinstance(pr.get("head_sha"), str) and pr.get("head_sha") else None
    if head is None and isinstance(rec.get("head_sha"), str) and rec.get("head_sha"):
        head = rec["head_sha"]
    return repo, number, head


def _fail(path: Path, line: int, reason: str) -> None:
    raise HandCheckError(f"{path.name} line {line}: {reason}")


def _check_row(path: Path, line: int, row) -> tuple[str, int, str]:
    if not isinstance(row, dict):
        _fail(path, line, "each line must be a JSON object")
    extra = [key for key in row if key not in FIELDS]
    missing = [key for key in FIELDS if key not in row]
    if extra or missing:
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("unexpected " + ", ".join(extra))
        _fail(path, line, "; ".join(detail))
    repo, pr, head, base = row["repo"], row["pr"], row["head"], row["base"]
    if not isinstance(repo, str) or not REPO.match(repo):
        _fail(path, line, "repo must be owner/name")
    if type(pr) is not int or pr <= 0:
        _fail(path, line, "pr must be a positive integer")
    if not isinstance(head, str) or not SHA.match(head):
        _fail(path, line, "head must be a 40-character commit")
    if not isinstance(base, str) or not SHA.match(base):
        _fail(path, line, "base must be a 40-character commit")
    if not isinstance(row["date"], str) or not DATE.match(row["date"]):
        _fail(path, line, "date must be YYYY-MM-DD")
    if row["checker_verdict"] not in CHECKER_VERDICTS:
        _fail(path, line, "checker_verdict must be verified, needs_attention, or could_not_verify")
    note = row["checker_note"]
    if note is not None and not isinstance(note, str):
        _fail(path, line, "checker_note must be text or null")
    if type(row["broken"]) is not bool:
        _fail(path, line, "broken must be true or false")
    if row["tool_verdict"] is not None and row["tool_verdict"] not in CHECKER_VERDICTS:
        _fail(path, line, "tool_verdict must be a verdict or null")
    if row["score"] not in SCORES:
        _fail(path, line, "score must be agree, false_alarm, miss, settled_abstention, or other")
    commit = row["poc_commit"]
    if commit is not None and (not isinstance(commit, str) or not POC_COMMIT.match(commit)):
        _fail(path, line, "poc_commit must be a commit id or null")
    if not isinstance(row["source"], str) or not row["source"].strip():
        _fail(path, line, "source must be text")
    earlier = row["also_checked"]
    if earlier is not None and (
            not isinstance(earlier, list) or any(not isinstance(item, str) or not DATE.match(item) for item in earlier)):
        _fail(path, line, "also_checked must be a list of dates or null")
    return repo, pr, head


def load_hand_checks(path: Path) -> dict[tuple[str, int, str], dict]:
    """Rows keyed by repository, pull request, and head. A bad row or a repeated key fails."""
    path = Path(path)
    try:
        text = path.read_text()
    except OSError as exc:
        raise HandCheckError(f"{path.name} could not be read") from exc
    found: dict[tuple[str, int, str], dict] = {}
    seen_at: dict[tuple[str, int, str], int] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            _fail(path, number, f"not JSON ({exc.msg})")
        key = _check_row(path, number, row)
        if key in found:
            _fail(path, number, f"repeated pull request {key[0]}#{key[1]} at {key[2]} (also on line {seen_at[key]})")
        found[key] = row
        seen_at[key] = number
    return found


def _pull_key(rec: dict) -> tuple:
    """One pull request, ignoring head, so several records of it can count once in the verdict table."""
    repo, number, _head = record_identity(rec)
    if repo and number is not None:
        return ("pr", repo, number)
    return ("source", str(rec.get("_source") or ""))


def collapse(records: list[dict]) -> list[dict]:
    """One entry per pull request. The stored verdict is the one on the last record in path order."""
    groups: dict[tuple, list[dict]] = {}
    for rec in records:
        groups.setdefault(_pull_key(rec), []).append(rec)
    out = []
    for key in sorted(groups):
        rows = sorted(groups[key], key=lambda rec: str(rec.get("_source") or ""))
        chosen = rows[-1]
        repo, number, head = record_identity(chosen)
        out.append({
            "key": key,
            "records": len(rows),
            "verdict": shown_verdict(chosen),
            "verified": shown_verdict(chosen) == "verified",
            "repo": repo,
            "pr": number,
            "head": head,
        })
    return out


def assess_saved(records: list[dict], labels: dict | None) -> dict:
    """Verdict counts, wrong passes, and the false-confirmation rate. labels None means the file is absent."""
    record_counts = Counter(shown_verdict(rec) for rec in records)
    prs = collapse(records)
    pr_counts = Counter(row["verdict"] for row in prs)
    available = labels is not None
    labelled = []
    wrong = []
    unlabelled = []
    if available:
        grouped: dict[tuple, list[dict]] = {}
        for rec in records:
            grouped.setdefault(_pull_key(rec), []).append(rec)
        for key in sorted(grouped):
            verified_rows = [rec for rec in grouped[key] if shown_verdict(rec) == "verified"]
            if not verified_rows:
                continue
            matched = []
            for rec in verified_rows:
                repo, number, head = record_identity(rec)
                if repo and number is not None and head:
                    label = labels.get((repo, number, head))
                    if label is not None:
                        matched.append((repo, number, label))
            if not matched:
                unlabelled.append(key)
                continue
            labelled.append(key)
            if any(label["broken"] is True for _repo, _number, label in matched):
                wrong.append(matched[0][0] + "#" + str(matched[0][1]))
    return {
        "available": available,
        "record_verdicts": {name: record_counts.get(name, 0) for name in VERDICT_ORDER},
        "pull_request_verdicts": {name: pr_counts.get(name, 0) for name in VERDICT_ORDER},
        "records": len(records),
        "pull_requests": len(prs),
        "wrong_passes": rate(len(wrong), len(labelled)) if available else None,
        "false_confirmations": rate(len(wrong), len(labelled)) if available else None,
        "unlabelled": len(unlabelled) if available else None,
        "wrong_pass_prs": wrong if available else [],
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


def _matched_labels(records: list[dict], labels: dict) -> list[dict]:
    """Hand-check rows for verified records whose repository, pull request, and head all match."""
    matched = []
    for rec in records:
        if shown_verdict(rec) != "verified":
            continue
        repo, number, head = record_identity(rec)
        if repo and number is not None and head:
            label = labels.get((repo, number, head))
            if label is not None:
                matched.append(label)
    return matched


def arm_rates(rows: list[dict], by_case: dict[str, list[dict]], labels: dict) -> dict:
    """False confirmations for one arm. Each case is one pull request. Record fields are not labels.

    Every verified record of the case is checked. One matching broken label makes the case a wrong pass.
    """
    wrong = labelled = unlabelled = 0
    for row in rows:
        recs = by_case.get(row.get("case_id"), [])
        verified_recs = [rec for rec in recs if shown_verdict(rec) == "verified"]
        result_verified = row.get("outcome") == "ran" and row.get("verdict") == "verified"
        if not verified_recs and not result_verified:
            continue
        matched = _matched_labels(verified_recs, labels)
        if not matched:
            unlabelled += 1
            continue
        labelled += 1
        if any(label["broken"] is True for label in matched):
            wrong += 1
    return {
        "wrong_passes": rate(wrong, labelled),
        "false_confirmations": rate(wrong, labelled),
        "unlabelled": unlabelled,
    }


def attach(root: Path, arms: dict[str, list[dict]], summary: dict, checks: Path | None = None) -> dict:
    """Copy of summary plus the hand-check rates. The results folder is only read."""
    path = DEFAULT_HAND_CHECKS if checks is None else Path(checks)
    out = dict(summary)
    if not path.is_file():
        out["accuracy"] = {"available": False}
        return out
    labels = load_hand_checks(path)
    by_case = records_by_case(root)
    out["accuracy"] = {
        "available": True,
        "arms": {arm: arm_rates(rows, by_case, labels) for arm, rows in arms.items()},
    }
    return out


def _fmt(block: dict | None) -> str:
    if not block or not block.get("n"):
        return "n/a (n=0)"
    return f"{block['count']}/{block['n']}"


def accuracy_paragraph(accuracy: dict) -> str:
    """Plain-language lines placed under the benchmark table."""
    if not accuracy.get("available"):
        return "\nHand checks not available.\n"
    lines = [
        "",
        "Every verified record of a pull request is checked. "
        "A label counts only when that record's repository, pull request, and head commit all match. "
        "A label for one head is not applied to a record at another head.",
    ]
    for arm, block in accuracy.get("arms", {}).items():
        lines.append(
            f"{arm}: wrong passes {block['wrong_passes']['count']}; "
            f"false confirmations {_fmt(block['false_confirmations'])}; "
            f"unlabelled verified pull requests {block['unlabelled']}."
        )
    lines.append(
        "A wrong pass is a verified pull request whose hand check says it really breaks something. "
        "The false-confirmation rate counts those pull requests over the verified pull requests that have a matching hand check. "
        "A verified pull request with no matching hand check is unlabelled, not a pass."
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
        "The pull-request table uses the stored verdict on the last record in path order. "
        "Wrong passes look at every verified record of that pull request."
    )
    lines.append("")
    if not stats["available"]:
        lines.append("Hand checks not available.")
        lines.append("")
        return "\n".join(lines)
    lines.append(
        "A hand check counts only for a verified record whose repository, pull request, and head commit all match. "
        "A label for one head is not applied to a record at another head."
    )
    lines.append("")
    lines.append(f"Wrong passes: {stats['wrong_passes']['count']}.")
    lines.append(f"False confirmations: {_fmt(stats['false_confirmations'])}.")
    lines.append(f"Unlabelled verified pull requests: {stats['unlabelled']}.")
    lines.append("")
    lines.append(
        "A wrong pass is a verified pull request whose hand check says it really breaks something. "
        "The false-confirmation rate counts those pull requests over the verified pull requests that have a matching hand check. "
        "A verified pull request with no matching hand check is unlabelled, not a pass."
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


def saved_report(root: Path, checks: Path | None = None) -> str:
    """Report for saved records. checks defaults to data/hand_checks.jsonl in this repository."""
    path = DEFAULT_HAND_CHECKS if checks is None else Path(checks)
    labels = load_hand_checks(path) if path.is_file() else None
    return saved_markdown(assess_saved(read_saved(root), labels))
