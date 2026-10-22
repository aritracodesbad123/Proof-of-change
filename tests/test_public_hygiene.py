"""The repository is public: no file may name the people or bots behind it, internal schedules, internal tools, or
machine-local paths. This guard fails CI if any of them reappear in a tracked file (PDF text included when
pdftotext is available). The owner's handle may appear only in this repository's clone URL and its GitHub Pages
address."""
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
    # GitHub Pages uses the owner handle as the site name. The name still fails in prose.
    re.compile(r"aritracodesbad123\.github\.io/proof-of-change", re.I),
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
# owner/name, or the same pair in a github.com URL. Used only to recognise an upstream repository name.
UPSTREAM_REPO = re.compile(r"(?:https?://github\.com/)?[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", re.I)


def _under_study_pairs(path: Path | None) -> bool:
    """True when path is a file inside evals/study_pairs/."""
    if path is None:
        return False
    parts = path.parts
    return any(parts[i] == "evals" and i + 1 < len(parts) and parts[i + 1] == "study_pairs"
               for i in range(len(parts)))


def _under_random_prs(path: Path | None) -> bool:
    """True when path is a file inside benchmarks/random-prs/ (lists of upstream PRs)."""
    if path is None:
        return False
    parts = path.parts
    return any(parts[i] == "benchmarks" and i + 1 < len(parts) and parts[i + 1] == "random-prs"
               for i in range(len(parts)))


def _under_upstream_run(path: Path | None) -> bool:
    """True for stored upstream check results (batch run folders and the results-page replay data)."""
    if path is None:
        return False
    parts = path.parts
    for i in range(len(parts) - 1):
        if parts[i] == "benchmarks" and parts[i + 1].startswith("batch30-"):
            return True
        if parts[i] == "replay" and parts[i + 1] in {"checks", "catalog.json"}:
            return True
    return False


def _inside_upstream_repo(line: str, match: re.Match) -> bool:
    """True when the match sits inside an upstream repository name on this line."""
    return any(repo.start() <= match.start() and match.end() <= repo.end() for repo in UPSTREAM_REPO.finditer(line))


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


def findings(text: str, path: Path | None = None) -> list[str]:
    for a in ALLOWED:
        text = a.sub("<repo-url>", text)
    study_pairs = _under_study_pairs(path) or _under_random_prs(path)
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for kind, pat in PATTERNS.items():
            matches = list(pat.finditer(line))
            if kind in {"bot", "internal library registry / picks"} and _under_upstream_run(path):
                # Upstream package, test and repository names in stored run output. Machine paths still fail.
                matches = []
            if kind == "bot" and study_pairs:
                # Repository names under the study-pair files may contain this word. Prose still fails.
                matches = [m for m in matches if not _inside_upstream_repo(line, m)]
            if matches:
                out.append(f"line {i}: {kind}: {matches[0].group(0)!r}")
    return out


def test_no_internal_names_or_paths_in_tracked_files():
    bad = {}
    for p in tracked_files():
        t = text_of(p)
        if t is not None:
            f = findings(t, p)
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
                                  "https://aritracodesbad123.github.io/Proof-of-change/",
                                  "*{box-sizing:border-box}", "a checkbox", "pick the tests", "cloud credits",
                                  "Nemotron robot-free", "Copyright (c) 2026 Aritra Chakraborty"])
def test_guard_allows(text):
    assert not findings(text)


def test_study_pair_repository_names_skip_only_that_word():
    """An upstream repository name under evals/study_pairs/ may contain the word. The same text elsewhere,
    and any other banned word in that folder, still fails."""
    repo = '{"repo": "python-telegram-bot/python-telegram-bot"}\n'
    inside = Path("evals/study_pairs/manifest.json")
    outside = Path("docs/notes.md")
    assert not findings(repo, inside)
    assert findings(repo, outside)
    assert findings(repo)  # no path: the exception does not apply
    assert findings("the ops bot\n", inside)
    assert findings('{"repo": "Acme/Nathan"}\n', inside)
    assert findings("see python-telegram-bot here\n", inside)  # a bare name is not owner/name
    mixed = "python-telegram-bot/python-telegram-bot and the ops bot\n"
    assert findings(mixed, inside)
