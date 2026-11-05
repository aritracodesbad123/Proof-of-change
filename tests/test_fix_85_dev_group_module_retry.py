"""Fix 85: both-sides ModuleNotFoundError installs from any dependency-group / optional-dep.

Covers:
- isort #2781 shape (base 841e4312 / head 3936b83f): hypothesis and black live only in
  ``[dependency-groups] dev``, not in a test/tests/testing extra.
- A held-out repo whose only match is a ``dev`` group entry (no per-repo cases, no fixed maps).
"""
from __future__ import annotations

from pathlib import Path

from poc import demo_helper

# Real isort #2781 SHAs Jonathan named; the fixture mirrors pyproject at the base.
ISORT_BASE = "841e4312"
ISORT_HEAD = "3936b83f"

ISORT_PYPROJECT = """
[project]
name = "isort"
version = "7.0.0"
dependencies = ["tomli>=2; python_version < \\"3.11\\""]

[project.optional-dependencies]
colors = ["colorama"]

[dependency-groups]
dev = [
    "bandit>=1.8.6",
    "black>=25.9.0",
    "hypothesis>=6.140.3",
    "pytest>=8.4.2",
]
docs = [
    "myst-parser>=4.0.1",
    "sphinx>=7.4.7",
]
"""

# Snippet shaped like the real pytest-main-1 / pytest-pr-1 logs for isort #2781.
ISORT_LOG = """
==================================== ERRORS ====================================
__________________ ERROR collecting tests/unit/test_output.py __________________
E   ModuleNotFoundError: No module named 'hypothesis'
=================================== FAILURES ===================================
____________ test_sort_reexports_output_is_black_stable_issue_2280 _____________
E       ModuleNotFoundError: No module named 'black'
tests/unit/test_regressions.py:2499: ModuleNotFoundError
"""


def _write_both_logs(root: Path, text: str) -> Path:
    logs = root / "logs"
    logs.mkdir()
    (logs / "pytest-main-1.log").write_text(text)
    (logs / "pytest-pr-1.log").write_text(text)
    return logs


def test_isort_2781_dev_group_modules_install_and_name_reason(tmp_path):
    """isort #2781 (base {base}, head {head}): install hypothesis+black from [dependency-groups] dev.""".format(
        base=ISORT_BASE, head=ISORT_HEAD
    )
    (tmp_path / "pyproject.toml").write_text(ISORT_PYPROJECT)
    logs = _write_both_logs(tmp_path, ISORT_LOG)

    both = demo_helper.modules_missing_on_both_sides(logs)
    assert both == ["hypothesis", "black"]
    assert demo_helper.requirement_for_module_anywhere(tmp_path, "hypothesis") == "hypothesis>=6.140.3"
    assert demo_helper.requirement_for_module_anywhere(tmp_path, "black") == "black>=25.9.0"
    # colors / docs extras must not invent a map; sphinx is only listed, not missing on both sides
    assert demo_helper.requirement_for_module_anywhere(tmp_path, "sphinx") == "sphinx>=7.4.7"

    calls = []

    def install_one(side, requirement):
        calls.append((side, requirement))
        return True, "9.9.9"

    def rerun():
        calls.append("rerun")
        return {"verdict": "verified", "reason": "the tests passed after the install"}

    rec = {
        "verdict": "could_not_verify",
        "reason": "fail to load on both sides",
        "library": "isort",
    }
    demo_helper.retry_unverified_study(
        rec, rerun, install_one, [], "", lambda _name: None, "PyCQA/isort",
        log_dir=logs, checkouts=[tmp_path],
    )
    assert ("main", "hypothesis>=6.140.3") in calls
    assert ("pr", "hypothesis>=6.140.3") in calls
    assert ("main", "black>=25.9.0") in calls
    assert ("pr", "black>=25.9.0") in calls
    assert "rerun" in calls
    assert rec["verdict"] == "verified"
    installed = [row["package"] for row in (rec["demo_helper"]["gap_retry"]["installed"] or [])]
    assert installed == ["hypothesis", "black"]
    notes = "\n".join(rec["demo_helper"]["notes"])
    assert "hypothesis" in notes and "black" in notes


def test_isort_2781_names_module_in_reason_when_still_missing(tmp_path):
    (tmp_path / "pyproject.toml").write_text(ISORT_PYPROJECT)
    logs = _write_both_logs(tmp_path, ISORT_LOG)

    def install_one(_side, _requirement):
        return True, "9.9.9"

    def still_missing():
        return {
            "verdict": "could_not_verify",
            "reason": "ModuleNotFoundError: No module named 'hypothesis'",
        }

    rec = {"verdict": "could_not_verify", "reason": "fail to load on both sides", "library": "isort"}
    demo_helper.retry_unverified_study(
        rec, still_missing, install_one, [], "", lambda _name: None, "PyCQA/isort",
        log_dir=logs, checkouts=[tmp_path],
    )
    assert rec["verdict"] == "could_not_verify"
    assert "hypothesis" in rec["reason"]
    assert rec["reason"].startswith("could not verify: setup gap hypothesis")


def test_held_out_dev_group_only_dependency(tmp_path):
    """Held-out repo: the missing module is listed only under [dependency-groups] dev."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "held-out-widgets"
version = "0.1.0"
dependencies = ["requests>=2"]

[project.optional-dependencies]
# deliberately no test/tests/testing extra
colors = ["colorama"]

[dependency-groups]
dev = [
    "fancycheck>=2.1.0",
]
"""
    )
    logs = _write_both_logs(
        tmp_path,
        "E   ModuleNotFoundError: No module named 'fancycheck'\n",
    )
    assert demo_helper.modules_missing_on_both_sides(logs) == ["fancycheck"]
    assert demo_helper.requirement_for_module_anywhere(tmp_path, "fancycheck") == "fancycheck>=2.1.0"

    calls = []

    def install_one(side, requirement):
        calls.append((side, requirement))
        return True, "2.1.0"

    def rerun():
        calls.append("rerun")
        return {"verdict": "needs_attention", "reason": "one new failure after the install"}

    rec = {"verdict": "could_not_verify", "reason": "fail to load on both sides", "library": "held-out-widgets"}
    demo_helper.retry_unverified_study(
        rec, rerun, install_one, [], "", lambda _name: None, "acme/held-out-widgets",
        log_dir=logs, checkouts=[tmp_path],
    )
    assert calls == [("main", "fancycheck>=2.1.0"), ("pr", "fancycheck>=2.1.0"), "rerun"]
    assert rec["verdict"] == "needs_attention"
    assert any(row["package"] == "fancycheck" for row in rec["demo_helper"]["gap_retry"]["installed"])


def test_one_side_only_does_not_treat_as_both(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\nversion='1'\ndependencies=[]\n"
        "[dependency-groups]\ndev=['fancycheck>=1']\n"
    )
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "pytest-main-1.log").write_text("E   ModuleNotFoundError: No module named 'fancycheck'\n")
    (logs / "pytest-pr-1.log").write_text("all green\n")
    assert demo_helper.modules_missing_on_both_sides(logs) == []


def test_product_path_also_installs_from_dev_group(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\nversion='1'\ndependencies=[]\n"
        "[dependency-groups]\ndev=['fancycheck>=2.1.0']\n"
    )
    logs = _write_both_logs(tmp_path, "E   ModuleNotFoundError: No module named 'fancycheck'\n")
    calls = []

    def install_one(side, requirement):
        calls.append((side, requirement))
        return True, "2.1.0"

    def rerun():
        calls.append("rerun")
        return {"verdict": "verified", "reason": "ok"}

    rec = {"verdict": "could_not_verify", "reason": "fail to load on both sides"}
    demo_helper.retry_unverified(
        rec, rerun, install_one, [], "", lambda _name: None, "acme/x",
        log_dir=logs, checkouts=[tmp_path], product_repair=True, max_tries=1,
    )
    assert ("main", "fancycheck>=2.1.0") in calls
    assert ("pr", "fancycheck>=2.1.0") in calls
    assert "rerun" in calls
    assert rec["verdict"] == "verified"
    # The try log names the module, not a bare "setup"
    tries = rec["demo_helper"]["gap_retry"]["tries"]
    assert tries[0]["problem"] == "fancycheck"
