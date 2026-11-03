"""The public-file check: the same rules the repository applies to files on main.

Patterns are built from pieces so this file does not itself contain the text it forbids.
"""
from __future__ import annotations

import re
from pathlib import Path


def _j(*parts: str) -> str:
    return "".join(parts)


_HANDLE = _j("ari", "tra", "codes", "bad", "123")
_KIND_BOT = _j("bo", "t")
_KIND_PICKS = _j("internal library ", "reg", "istry / ", "pi", "cks")
ALLOWED = [
    re.compile(_j(r"github\.com/", _HANDLE, r"/proof-of-change(\.git)?"), re.I),
    re.compile(_j(_HANDLE, r"\.github\.io/proof-of-change"), re.I),
    re.compile(_j(r"Copyright \(c\) 2026 ", "Ari", "tra", " Chakra", "borty")),
]
BANNED = {
    "team member name": _j(r"\b(", "na", "than", "|", "jon", "athan", "|", "ari", "tra", r")\b|",
                           "ari", "tra", r"(?!", "codes", "bad", "123", r"/proof-of-change)"),
    _j("bo", "t"): _j(r"\b", "bo", r"ts?\b|", "gro", "k"),
    "internal schedule": _j(r"\b", "10", r":15\b|\b", "11", r":15\b"),
    _KIND_PICKS: _j("reg", "istry", r"|\b", "pi", "cks", r"\b"),
    "internal machine": _j("shared", " ", "machine", r"|(?<![\w-])", "bo", "x", r"(?![\w-])|/",
                           "work", "space", r"\b|/", "home", "/", "bo", "x"),
    "internal tool": _j("validation", " ", "center"),
    "personal credit": _j(r"\b", "cre", "dit", r"(ed|s)? (to|by)\b"),
}
PATTERNS = {k: re.compile(v, re.I) for k, v in BANNED.items()}
UPSTREAM_REPO = re.compile(r"(?:https?://github\.com/)?[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", re.I)


def _under_study_pairs(path: Path | None) -> bool:
    """True when path is a file inside evals/study_pairs/."""
    if path is None:
        return False
    parts = path.parts
    return any(parts[i] == "evals" and i + 1 < len(parts) and parts[i + 1] == "study_pairs"
               for i in range(len(parts)))


def _under_random_prs(path: Path | None) -> bool:
    """True inside benchmarks/random-prs/ or benchmarks/batch30-*/."""
    if path is None:
        return False
    parts = path.parts
    return any(parts[i] == "benchmarks" and i + 1 < len(parts)
               and (parts[i + 1] == "random-prs" or parts[i + 1].startswith("batch30-"))
               for i in range(len(parts)))


def _under_upstream_run(path: Path | None) -> bool:
    """True only for stored upstream run output: the tool's own record and report files."""
    if path is None:
        return False
    parts = path.parts
    for i in range(len(parts) - 1):
        if (parts[i] == "benchmarks" and parts[i + 1].startswith("batch30-") and "runs" in parts[i + 2:-1]
                and path.name in {"record.json", "REPORT.md", "REPORT.html"}):
            return True
        if parts[i] == "replay" and parts[i + 1] == "catalog.json":
            return True
        if parts[i] == "replay" and parts[i + 1] == "checks" and path.name in {"record.json", "REPORT.md", "REPORT.html"}:
            return True
    return False


def _inside_upstream_repo(line: str, match: re.Match) -> bool:
    """True when the match sits inside an upstream repository name on this line."""
    return any(repo.start() <= match.start() and match.end() <= repo.end() for repo in UPSTREAM_REPO.finditer(line))


def _keep_match(kind: str, line: str, match: re.Match, path: Path | None) -> bool:
    study_pairs = _under_study_pairs(path) or _under_random_prs(path)
    if kind in {_KIND_BOT, _KIND_PICKS} and _under_upstream_run(path):
        return True
    if kind == _KIND_BOT and study_pairs and _inside_upstream_repo(line, match):
        return True
    return False


def findings(text: str, path: Path | None = None) -> list[str]:
    """Lines that the public check would reject. Same rules as the check on main."""
    for allowed in ALLOWED:
        text = allowed.sub("<repo-url>", text)
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for kind, pat in PATTERNS.items():
            bad = [m for m in pat.finditer(line) if not _keep_match(kind, line, m, path)]
            if bad:
                out.append(f"line {i}: {kind}: {bad[0].group(0)!r}")
    return out


def scrub_public_text(text: str, path: Path | None = None) -> str:
    """Replace text the public check would reject. Allowed repository addresses are left as they are."""
    protected: list[str] = []

    def park(match: re.Match) -> str:
        protected.append(match.group(0))
        return f"\x00{len(protected) - 1}\x00"

    parked = text
    for allowed in ALLOWED:
        parked = allowed.sub(park, parked)
    lines = []
    for line in parked.splitlines():
        for kind, pat in PATTERNS.items():
            line = pat.sub(lambda m, kind=kind, line=line: m.group(0) if _keep_match(kind, line, m, path) else " ", line)
        lines.append(line)
    out = "\n".join(lines)
    if text.endswith("\n"):
        out += "\n"
    return re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], out)
