"""Gather the ordered main-study pair list.

A pair is one agent-written pull request and one human-written pull request in the
same repository. The matching rules live in the rules file (seed, cap, and the
checks below). This program does not loosen those checks to fill the list.

A missing patch file skips that candidate. The patch is never invented or rebuilt.
Expected verdicts and labels are refused before any row is used.

    python -m evals.gather_study_pairs --candidates candidates.csv \\
        --rules evals/study_pair_rules.json \\
        --out evals/study_pairs/main-study-pairs.json \\
        --manifest evals/study_pairs/manifest.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from pathlib import Path

from ops.bench import ANSWER_COLUMNS, AnswerKeyRefused, guard_path

DIFF_FILE = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.M)
COLUMNS = ("repo", "agent_pr", "human_pr", "agent_patch", "human_patch")
# Column names that would carry an expected verdict or a label. The cell values are never read.
LEAK_NAMES = set(ANSWER_COLUMNS) | {"verdict", "expected", "expected_verdict", "ground_truth"}


class StudyPairError(ValueError):
    """The candidate file or the rules file cannot be used."""


def load_rules(path: str | Path) -> dict:
    """The matching rules. A missing patch must stay a skip, never a rebuilt patch."""
    data = json.loads(Path(path).read_text())
    required = ("seed", "cap", "require_same_repo", "require_distinct_prs", "require_patch_file",
                "require_shared_changed_file", "reconstruct_missing_patch")
    missing = [k for k in required if k not in data]
    if missing:
        raise StudyPairError(f"rules file is missing {', '.join(missing)}")
    if data["reconstruct_missing_patch"] is not False:
        raise StudyPairError("rules must keep reconstruct_missing_patch false")
    if not isinstance(data["seed"], int) or isinstance(data["seed"], bool):
        raise StudyPairError("rules seed must be an integer")
    if not isinstance(data["cap"], int) or isinstance(data["cap"], bool) or data["cap"] < 0:
        raise StudyPairError("rules cap must be zero or more")
    return data


def _leak_columns(names: list[str] | None) -> list[str]:
    bad = []
    for name in names or []:
        key = name.strip().lower()
        if key in LEAK_NAMES or "verdict" in key or key.startswith("expected") or key == "label":
            bad.append(name)
    return bad


def read_candidates(path: str | Path, root: Path | None = None) -> list[dict]:
    """Proposed pairs. Verdict and label columns refuse the file before any value is used."""
    p = guard_path(path)
    base = root if root is not None else p.parent
    with open(p, newline="") as fh:
        rd = csv.DictReader(fh)
        leaked = _leak_columns(rd.fieldnames)
        if leaked:
            raise AnswerKeyRefused(
                f"{p.name} has verdict or label columns ({', '.join(leaked)}); those values are not read")
        missing = [c for c in COLUMNS if c not in (rd.fieldnames or [])]
        if missing:
            raise StudyPairError(f"{p.name}: missing column(s) {', '.join(missing)}")
        rows = []
        for raw in rd:
            repo = (raw.get("repo") or "").strip()
            rows.append({
                "repo": repo,
                "agent_pr": (raw.get("agent_pr") or "").strip(),
                "human_pr": (raw.get("human_pr") or "").strip(),
                "agent_patch": str(base / (raw.get("agent_patch") or "").strip()),
                "human_patch": str(base / (raw.get("human_patch") or "").strip()),
            })
    return rows


def changed_files(text: str) -> list[str]:
    """Paths named by the diff headers. The patch text is not kept."""
    return [m.group(2) for m in DIFF_FILE.finditer(text)]


def _read_patch(path: str) -> tuple[str | None, str | None]:
    """Return (text, reason). A missing file is a skip. Nothing is written."""
    file = Path(path)
    if not file.is_file():
        return None, "missing_patch"
    text = file.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return None, "empty_patch"
    if not changed_files(text):
        return None, "not_a_diff"
    return text, None


def _exclude(row: dict, reason: str, side: str | None = None) -> dict:
    item = {"repo": row["repo"], "agent_pr": row["agent_pr"], "human_pr": row["human_pr"], "reason": reason}
    if side:
        item["side"] = side
    return item


def match_candidates(rows: list[dict], rules: dict) -> tuple[list[dict], list[dict]]:
    """Apply the rules. Missing patches are skipped. The patch file is never created."""
    matched = []
    excluded = []
    seen = set()
    for row in rows:
        repo_ok = "/" in row["repo"] and " " not in row["repo"]
        if rules["require_same_repo"] and not repo_ok:
            excluded.append(_exclude(row, "different_repo"))
            continue
        if rules["require_distinct_prs"] and (
                not row["agent_pr"].isdigit() or not row["human_pr"].isdigit()
                or row["agent_pr"] == row["human_pr"]):
            excluded.append(_exclude(row, "same_pull_request"))
            continue
        key = (row["repo"], row["agent_pr"], row["human_pr"])
        if key in seen:
            excluded.append(_exclude(row, "duplicate"))
            continue
        if rules["require_patch_file"]:
            agent_text, agent_why = _read_patch(row["agent_patch"])
            if agent_why:
                excluded.append(_exclude(row, agent_why, "agent"))
                continue
            human_text, human_why = _read_patch(row["human_patch"])
            if human_why:
                excluded.append(_exclude(row, human_why, "human"))
                continue
        else:
            agent_text, human_text = "", ""
        if rules["require_shared_changed_file"]:
            shared = set(changed_files(agent_text or "")) & set(changed_files(human_text or ""))
            if not shared:
                excluded.append(_exclude(row, "no_shared_file"))
                continue
        seen.add(key)
        matched.append({"repo": row["repo"], "agent_pr": int(row["agent_pr"]), "human_pr": int(row["human_pr"])})
    matched.sort(key=lambda p: (p["repo"], p["agent_pr"], p["human_pr"]))
    random.Random(rules["seed"]).shuffle(matched)
    cap = rules["cap"]
    kept, overflow = matched[:cap], matched[cap:]
    for item in overflow:
        excluded.append({"repo": item["repo"], "agent_pr": str(item["agent_pr"]),
                         "human_pr": str(item["human_pr"]), "reason": "over_cap"})
    excluded.sort(key=lambda e: (e["repo"], e["agent_pr"], e["human_pr"], e["reason"], e.get("side") or ""))
    return kept, excluded


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exclusion_counts(excluded: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in excluded:
        counts[item["reason"]] = counts.get(item["reason"], 0) + 1
    return dict(sorted(counts.items()))


def write_list(pairs: list[dict], excluded: list[dict], rules_path: Path, list_path: Path,
               manifest_path: Path, rules: dict) -> dict:
    """Write the ordered list and a manifest that names every exclusion and both hashes."""
    list_path.parent.mkdir(parents=True, exist_ok=True)
    list_path.write_text(json.dumps(pairs, indent=2) + "\n")
    manifest = {
        "cap": rules["cap"],
        "seed": rules["seed"],
        "matched": len(pairs),
        "exclusion_counts": exclusion_counts(excluded),
        "exclusions": excluded,
        "rules_sha256": _sha256(Path(rules_path).read_bytes()),
        "list_sha256": _sha256(list_path.read_bytes()),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def breakdown(manifest: dict) -> str:
    lines = [f"matched {manifest['matched']} (cap {manifest['cap']}, seed {manifest['seed']})"]
    counts = manifest["exclusion_counts"]
    if not counts:
        lines.append("exclusions: none")
    else:
        lines.append("exclusions: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    lines.append(f"rules_sha256 {manifest['rules_sha256']}")
    lines.append(f"list_sha256 {manifest['list_sha256']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gather the ordered main-study pair list.")
    ap.add_argument("--candidates", required=True, type=Path,
                    help="CSV of proposed pairs: repo, agent_pr, human_pr, agent_patch, human_patch")
    ap.add_argument("--rules", required=True, type=Path, help="matching rules JSON (hashed into the manifest)")
    ap.add_argument("--out", required=True, type=Path, help="ordered pair list JSON")
    ap.add_argument("--manifest", required=True, type=Path, help="counts, exclusions, and SHA-256 hashes")
    ap.add_argument("--root", type=Path, default=None, help="base directory for patch paths (default: the CSV directory)")
    a = ap.parse_args(argv)
    try:
        rules = load_rules(a.rules)
        rows = read_candidates(a.candidates, a.root)
        pairs, excluded = match_candidates(rows, rules)
        manifest = write_list(pairs, excluded, a.rules, a.out, a.manifest, rules)
    except (AnswerKeyRefused, StudyPairError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(breakdown(manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
