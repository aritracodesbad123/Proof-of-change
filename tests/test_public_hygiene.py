"""The repository is public: no file may name the people or bots behind it, internal schedules, internal tools, or
machine-local paths. This guard fails CI if any of them reappear in a tracked file (PDF text included when
pdftotext is available). Only the repository's own clone URL may contain the owner's handle."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()
ALLOWED = [
    re.compile(r"github\.com/aritracodesbad123/proof-of-change(\.git)?", re.I),
    # The licence file carries this copyright line on purpose. The name still fails anywhere else.
    re.compile(r"Copyright \(c\) 2026 Aritra Chakraborty"),
]
BANNED = {
    "team member name": r"\b(nathan|jonathan|aritra)\b|aritra(?!codesbad123/proof-of-change)",
    "bot": r"\bbots?\b|grok",
    "internal schedule": r"\b10:15\b|\b11:15\b",
    "internal library registry / picks": r"registry|\bpicks\b",
    "internal machine": r"shared machine|(?<![\w-])box(?![\w-])|/workspace\b|/home/box",
    "internal tool": r"validation center",
    "personal credit": r"\bcredit(ed|s)? (to|by)\b",
}
PATTERNS = {k: re.compile(v, re.I) for k, v in BANNED.items()}


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
        files = [ROOT / p for p in out.decode().split("\0") if p]
    except (OSError, subprocess.CalledProcessError):
        files = [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and ".venv" not in p.parts]
    skip = {".lock", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2"}
    skip_names = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
    return [p for p in files if p.exists() and p.resolve() != SELF
            and p.suffix.lower() not in skip and p.name not in skip_names]


def text_of(p: Path) -> str | None:
    if p.suffix.lower() == ".pdf":
        if not shutil.which("pdftotext"):
            if os.environ.get("CI"):
                pytest.fail("pdftotext is required in CI to scan committed PDFs")
            return None
        return subprocess.run(["pdftotext", str(p), "-"], capture_output=True).stdout.decode("utf-8", "replace")
    if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2"):
        return None
    return p.read_bytes().decode("utf-8", "replace")


def findings(text: str) -> list[str]:
    for a in ALLOWED:
        text = a.sub("<repo-url>", text)
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for kind, pat in PATTERNS.items():
            m = pat.search(line)
            if m:
                out.append(f"line {i}: {kind}: {m.group(0)!r}")
    return out


def test_no_internal_names_or_paths_in_tracked_files():
    bad = {}
    for p in tracked_files():
        t = text_of(p)
        if t is not None:
            f = findings(t)
            if f:
                bad[str(p.relative_to(ROOT))] = f[:3]
    assert not bad, "internal names/paths found (the repo is public):\n" + "\n".join(
        f"  {k}: {v}" for k, v in sorted(bad.items()))


@pytest.mark.parametrize("text", ["Thanks, Nathan", "jonathan@localhost", "Aritra merges", "the ops bot",
                                  "at 11:15 IST", "the registry", "Jonathan's picks", "on the shared machine",
                                  "on the box", "/workspace/x", "the Validation Center", "credit to J."])
def test_guard_catches(text):
    assert findings(text)


@pytest.mark.parametrize("text", ["git clone https://github.com/aritracodesbad123/Proof-of-change.git",
                                  "*{box-sizing:border-box}", "a checkbox", "pick the tests", "cloud credits",
                                  "Nemotron robot-free", "Copyright (c) 2026 Aritra Chakraborty"])
def test_guard_allows(text):
    assert not findings(text)
