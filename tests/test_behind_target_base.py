"""A pull request that is behind its target tip is compared at the merge-base.

Two local histories, no network. A target-only edit (a pin bump, a skipif change) must not be attributed to the
pull request, and the base that is checked out is the base setup, new tests and probes read. A pull request that
is not behind an older base keeps that base when a newer tip exists on another branch.
"""
import os
import shutil
import subprocess
from pathlib import Path

from bench import run as bench_run
from ops import daily_run
from poc import demo_helper, diff_probes


def _git(repo: Path, *args: str) -> str:
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.invalid", "HOME": str(repo), "PATH": os.environ.get("PATH", "")}
    got = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)
    return got.stdout.strip()


def _init(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


_PYPROJECT = """\
[project]
name = "widget"
version = "1"
dependencies = []

[project.optional-dependencies]
dev = ["helper=={pin}"]
"""

_TYPES = """\
import sys

import pytest


@pytest.mark.skipif(sys.version_info < {bound}, reason="old")
def test_types():
    assert True
"""

_MOD = """\
def value():
    return {n}
"""

_ADDED = """\
def test_added():
    assert True
"""


def _behind_history(tmp: Path) -> tuple[Path, dict]:
    """Fork M. The pull request changes pkg/mod.py and adds a test. The target tip later bumps a pin and a skipif."""
    repo = tmp / "src"
    _init(repo)
    _write(repo, "pyproject.toml", _PYPROJECT.format(pin="1.0"))
    _write(repo, "pkg/mod.py", _MOD.format(n=1))
    _write(repo, "tests/test_types.py", _TYPES.format(bound="(3, 8)"))
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fork")
    fork = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "pr")
    _write(repo, "pkg/mod.py", _MOD.format(n=2))
    _write(repo, "tests/test_added.py", _ADDED)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "pr")
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    _write(repo, "pyproject.toml", _PYPROJECT.format(pin="2.0"))
    _write(repo, "tests/test_types.py", _TYPES.format(bound="(3, 11)"))
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "target moved")
    tip = _git(repo, "rev-parse", "HEAD")
    return repo, {"fork": fork, "head": head, "tip": tip}


def _older_base_history(tmp: Path) -> tuple[Path, dict]:
    """The pull request targets an older base and is not behind it. main has since moved."""
    repo = tmp / "src"
    _init(repo)
    _write(repo, "pyproject.toml", _PYPROJECT.format(pin="1.0"))
    _write(repo, "pkg/mod.py", _MOD.format(n=0))
    _write(repo, "tests/test_types.py", _TYPES.format(bound="(3, 8)"))
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "older base")
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "branch", "release", base)
    _git(repo, "checkout", "-q", "-b", "pr")
    _write(repo, "pkg/mod.py", _MOD.format(n=5))
    _write(repo, "tests/test_added.py", _ADDED)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "pr on older base")
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    _write(repo, "pyproject.toml", _PYPROJECT.format(pin="9.0"))
    _write(repo, "tests/test_types.py", _TYPES.format(bound="(3, 12)"))
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "newer main")
    tip = _git(repo, "rev-parse", "HEAD")
    return repo, {"base": base, "head": head, "tip": tip}


def _env(tmp: Path) -> dict:
    return daily_run.base_env(tmp / "home")


def _place(repo: Path, work: Path) -> None:
    """The pinned checkout reads work/src and does not clone when that git dir already exists."""
    dest = work / "src"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(repo, dest, symlinks=True)


def _plan_pins(root: Path) -> list[str]:
    plan = demo_helper.build_setup_plan(
        "acme/widget", [root], {"text": ""}, "3.12", "local", "widget",
        python_available=lambda _version: None, pypi=lambda _name: None,
        docs_checkouts=[root], allow_lookup_packages=False)
    return [item["requirement"] for item in plan["packages"] if item.get("action") == "install"]


def test_skipif_context_is_not_a_changed_line():
    diff = """diff --git a/tests/test_types.py b/tests/test_types.py
--- a/tests/test_types.py
+++ b/tests/test_types.py
@@ -4,4 +4,4 @@ import pytest
 @pytest.mark.skipif(sys.version_info < (3, 8), reason="old")
 def test_types():
-    assert False
+    assert True
"""
    lines = daily_run.diff_new_lines(diff)
    assert lines["tests/test_types.py"] == {6}
    assert 4 not in lines["tests/test_types.py"]


def test_pr_behind_target_uses_merge_base_not_tip(tmp_path):
    repo, shas = _behind_history(tmp_path / "repo")
    env = _env(tmp_path)
    wrong = _git(repo, "diff", "--no-color", "--no-ext-diff", shas["tip"], shas["head"])
    wrong_lines = daily_run.diff_new_lines(wrong)
    assert "tests/test_types.py" in wrong_lines
    assert "helper==2.0" in wrong and "(3, 11)" in wrong

    choice = daily_run.comparison_choice(repo, env, head=shas["head"], supplied_base=shas["tip"],
                                         target_tip=shas["tip"])
    assert choice["main_sha"] == shas["fork"]
    assert choice["pr_sha"] == shas["head"]
    assert choice["behind_target"] is True
    assert choice["authoritative_base"] == "merge-base"
    assert choice["main_sha"] != shas["tip"]

    # The fork itself, passed explicitly, is already the right base. A newer tip does not replace it.
    kept = daily_run.comparison_choice(repo, env, head=shas["head"], supplied_base=shas["fork"],
                                       target_tip=shas["tip"])
    assert kept["explicit_base"] is True and kept["main_sha"] == shas["fork"]
    assert kept["main_sha"] != shas["tip"]

    work = tmp_path / "work"
    _place(repo, work)
    item = {"diff": wrong, "files": daily_run.classify_files(daily_run.diff_files(wrong), "pkg"),
            "head_sha": shas["head"], "current_head_sha": shas["head"],
            "pinned_sides": {"main": shas["tip"], "pr": shas["head"]}}
    assert daily_run.apply_pinned_diff("acme/widget", item, "pkg", work, tmp_path / "git.log") is None
    assert item["pinned_sides"]["main"] == shas["fork"]
    assert item["pinned_sides"]["supplied_main"] == shas["tip"]
    assert "tests/test_types.py" not in item["diff"]
    assert "helper==2.0" not in item["diff"]
    assert "return 2" in item["diff"]
    assert "tests/test_types.py" not in daily_run.diff_new_lines(item["diff"])
    assert 2 in daily_run.diff_new_lines(item["diff"])["pkg/mod.py"]
    assert daily_run.changed_test_files(item["files"]) == ["tests/test_added.py"]

    sp = daily_run.pinned_source_pair("acme/widget", item["pinned_sides"], work, tmp_path / "git.log")
    assert sp["ok"] and sp["main_sha"] == shas["fork"] and sp["pr_sha"] == shas["head"]
    assert sp["supplied_base_sha"] == shas["tip"] and sp["behind_target"] is True
    main_root, pr_root = work / "side-main", work / "side-pr"
    assert _git(main_root, "rev-parse", "HEAD") == shas["fork"]
    assert _git(pr_root, "rev-parse", "HEAD") == shas["head"]
    assert "helper==1.0" in (main_root / "pyproject.toml").read_text()
    assert "helper==2.0" not in (main_root / "pyproject.toml").read_text()
    assert "(3, 8)" in (main_root / "tests/test_types.py").read_text()
    assert "(3, 11)" not in (main_root / "tests/test_types.py").read_text()
    assert (pr_root / "pyproject.toml").read_text() == (main_root / "pyproject.toml").read_text()
    old = (main_root / "pkg/mod.py").read_text()
    new = (pr_root / "pkg/mod.py").read_text()
    assert daily_run.changed_lines_for_coverage(old, new) == {2}
    assert daily_run.changed_lines_for_coverage(
        (main_root / "tests/test_types.py").read_text(), (pr_root / "tests/test_types.py").read_text()) == set()
    pins = _plan_pins(main_root)
    assert "helper==1.0" in pins and all("helper==2.0" not in pin for pin in pins)
    derived = diff_probes.derive(item["diff"], ["pkg/mod.py"], main_root, [pr_root])
    assert ("pkg.mod", "value") in derived["targets"]
    assert "return 1" in (main_root / "pkg/mod.py").read_text()
    reqs, _cons = daily_run.pr_side_own_installs(["helper==1.0"], main_root, pr_root, None, "widget")
    assert reqs == ["helper==1.0"]

    case = {"base_sha": shas["tip"], "head_sha": shas["head"]}
    rec = {"chosen": {"head_sha": shas["head"]}, "sides": sp}
    assert bench_run.sha_check(case, rec) == []
    swapped = {"chosen": {"head_sha": shas["head"]},
               "sides": {"main_sha": "ab" * 20, "pr_sha": shas["head"]}}
    assert any("manifest base" in problem for problem in bench_run.sha_check(case, swapped))


def test_non_behind_pr_keeps_its_older_base(tmp_path):
    repo, shas = _older_base_history(tmp_path / "repo")
    env = _env(tmp_path)
    choice = daily_run.comparison_choice(repo, env, head=shas["head"], supplied_base=shas["base"],
                                         target_tip=shas["tip"])
    assert choice["explicit_base"] is True
    assert choice["main_sha"] == shas["base"]
    assert choice["main_sha"] != shas["tip"]
    assert choice["behind_target"] is False

    # Not behind the target tip either: the recorded base is that tip, so the later merge choice stands.
    assert daily_run.comparison_choice(repo, env, head=shas["head"], supplied_base=shas["base"],
                                       target_tip=shas["base"]) is None
    # A missing fetched tip must not become a reason to drop the ancestor the caller named.
    missing_tip = daily_run.comparison_choice(repo, env, head=shas["head"], supplied_base=shas["base"],
                                              target_tip="")
    assert missing_tip["main_sha"] == shas["base"] and missing_tip["explicit_base"] is True

    work = tmp_path / "work"
    _place(repo, work)
    item = {"diff": "diff --git a/not-the-pr b/not-the-pr\n", "files": {"all": ["not-the-pr"]},
            "head_sha": shas["head"], "current_head_sha": shas["head"],
            "pinned_sides": {"main": shas["base"], "pr": shas["head"]}}
    assert daily_run.apply_pinned_diff("acme/widget", item, "pkg", work, tmp_path / "git.log") is None
    assert item["pinned_sides"]["main"] == shas["base"]
    assert "helper==9.0" not in item["diff"]
    assert "(3, 12)" not in item["diff"]
    assert "return 5" in item["diff"]
    assert daily_run.changed_test_files(item["files"]) == ["tests/test_added.py"]
    assert "tests/test_types.py" not in daily_run.diff_new_lines(item["diff"])

    sp = daily_run.pinned_source_pair("acme/widget", item["pinned_sides"], work, tmp_path / "git.log")
    assert sp["ok"] and sp["main_sha"] == shas["base"] and sp["pr_sha"] == shas["head"]
    assert sp["behind_target"] is False and sp["explicit_base"] is True
    main_root = work / "side-main"
    assert _git(main_root, "rev-parse", "HEAD") == shas["base"]
    assert _git(main_root, "rev-parse", "HEAD") != shas["tip"]
    pins = _plan_pins(main_root)
    assert "helper==1.0" in pins and all("helper==9.0" not in pin for pin in pins)
    assert "(3, 8)" in (main_root / "tests/test_types.py").read_text()
    assert daily_run.changed_lines_for_coverage(
        (main_root / "pkg/mod.py").read_text(), (work / "side-pr" / "pkg/mod.py").read_text()) == {2}
