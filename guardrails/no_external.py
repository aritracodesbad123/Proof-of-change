"""Guardrail: Blast Radius must never post, file or push anything externally.

Static scan of the repository's Python and workflow files for calls that would
create something outside the box (issues, PRs, comments, pushes, emails, HTTP writes).
Reading (git clone, git ls-remote, pip/uv installs) is allowed.
A line can be exempted with the marker `# br-allow-external: <reason>` (reviewed in PRs).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

FORBIDDEN = [
    (r"\bgh\s+(issue|pr|release|api|gist)\b", "GitHub CLI write command"),
    (r"\bgit\s+push\b", "git push"),
    (r"requests\.(post|put|patch|delete)\(", "HTTP write via requests"),
    (r"httpx\.(post|put|patch|delete)\(", "HTTP write via httpx"),
    (r"method\s*=\s*['\"](POST|PUT|PATCH|DELETE)['\"]", "HTTP write via urllib"),
    (r"\bsmtplib\b", "email via smtplib"),
    (r"api\.github\.com/repos/[^\s'\"]*/(issues|pulls|comments)", "GitHub REST write endpoint"),
    (r"slack\.com/api/chat\.postMessage|hooks\.slack\.com", "Slack post"),
]
ALLOW_MARK = "br-allow-external:"
SCAN_GLOBS = ("**/*.py", ".github/workflows/*.yml", ".github/workflows/*.yaml", "**/*.sh")
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "cache", "runs", "__pycache__"}


def scan(root: str | Path) -> list[str]:
    root = Path(root)
    hits = []
    self_path = Path(__file__).resolve()
    for g in SCAN_GLOBS:
        for f in root.glob(g):
            if f.resolve() == self_path or SKIP_DIRS & set(f.relative_to(root).parts):
                continue
            for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                if ALLOW_MARK in line:
                    continue
                for pat, why in FORBIDDEN:
                    if re.search(pat, line):
                        hits.append(f"{f.relative_to(root)}:{n}: {why}: {line.strip()[:120]}")
    return sorted(set(hits))


if __name__ == "__main__":
    found = scan(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("\n".join(found) or "no external side effects found")
    sys.exit(1 if found else 0)
