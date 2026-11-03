"""The repository is public: no file may name the people or bots behind it, internal schedules, internal tools, or
machine-local paths. This guard fails CI if any of them reappear in a tracked file (PDF text included when
pdftotext is available). The owner's handle may appear only in this repository's clone URL and its GitHub Pages
address."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from guardrails.public_hygiene import findings

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()


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
