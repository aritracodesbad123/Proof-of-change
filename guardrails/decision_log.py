"""Decision-log check: a pull request that changes code must add a new decision-log entry.

Code means any file under poc/, harness/, evals/, guardrails/, reports/, ops/ or .github/. An entry is a NEW file
docs/decisions/YYYY-MM-DD-<short-topic>.md (lower-case letters, digits and hyphens in the topic). One file per pull
request, so parallel pull requests never edit the same file. See docs/decisions/README.md.

    python -m guardrails.decision_log --base origin/main        # compares the base branch with HEAD

Exit 0: no code changed, or a new entry was added. Exit 1: code changed without a new entry.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys

CODE_DIRS = ("poc/", "harness/", "evals/", "guardrails/", "reports/", "ops/", ".github/")
ENTRY_RE = re.compile(r"^docs/decisions/\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")


def check(changes: list[tuple[str, str]]) -> tuple[bool, str]:
    """changes: [(git status letter, path)] as from `git diff --name-status`. Returns (ok, message)."""
    code = sorted({p for _s, p in changes if p.startswith(CODE_DIRS)})
    added = sorted(p for s, p in changes if s.startswith("A") and ENTRY_RE.match(p))
    if not code:
        return True, "no code changed; no decision-log entry needed"
    if added:
        return True, f"decision-log entry added: {', '.join(added)}"
    bad = sorted(p for s, p in changes if s.startswith("A") and p.startswith("docs/decisions/") and not ENTRY_RE.match(p)
                 and not p.endswith("README.md"))
    hint = f" (these files do not match the name pattern: {', '.join(bad)})" if bad else ""
    return False, ("this change touches code (" + ", ".join(code[:5]) + (" ..." if len(code) > 5 else "")
                   + ") but adds no new decision-log entry: add docs/decisions/YYYY-MM-DD-<short-topic>.md, see "
                   "docs/decisions/README.md" + hint)


def parse_name_status(text: str) -> list[tuple[str, str]]:
    """`git diff --name-status` output -> [(status, path)]; a rename or copy counts as its new path."""
    out = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            out.append((parts[0], parts[-1]))
    return out


def changes_since(base: str) -> list[tuple[str, str]]:
    cp = subprocess.run(["git", "diff", "--name-status", f"{base}...HEAD"], capture_output=True, text=True, check=True)
    return parse_name_status(cp.stdout)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fail when code changes without a new decision-log entry.")
    ap.add_argument("--base", required=True, help="the pull request's base, e.g. origin/main")
    a = ap.parse_args(argv)
    ok, msg = check(changes_since(a.base))
    print(("OK: " if ok else "FAILED: ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
