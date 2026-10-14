"""Paired unreleased companions and the Hypothesis cap (2026-10-14 decision)."""
import subprocess
import sys

from ops import daily_run as d

PYJANITOR_LIKE = """
[project]
name = "pyjanitor"
dependencies = ["pandas>=3", "janitor-rs>=0.6.2,<0.7"]
[tool.pixi.pypi-dependencies]
pyjanitor = {path = ".", editable = true}
janitor-rs = {git = "https://github.com/pyjanitor-devs/janitor-rs.git", rev = "5449683"}
other = {git = "https://github.com/a/b.git", rev = "abcdef1"}
[tool.uv.sources]
evil = {git = "file:///etc", rev = "abcdef1"}
"""


def test_detects_only_declared_runtime_companions(tmp_path):
    (tmp_path / "pyproject.toml").write_text(PYJANITOR_LIKE)
    got = d.paired_git_dependencies(tmp_path)
    assert got == [{"name": "janitor-rs", "git": "https://github.com/pyjanitor-devs/janitor-rs.git", "rev": "5449683",
                    "source": "tool.pixi.pypi-dependencies"}]


def test_rejects_non_https_and_branch_revs(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="p"\ndependencies=["x"]\n'
                                             '[tool.uv.sources]\nx = {git = "https://g/a/x.git", rev = "main"}\n')
    assert d.paired_git_dependencies(tmp_path) == []


def test_combine_both_runs():
    def verdict(a, b):
        return d.combine_paired_verdicts([
            {"variant": "pip-resolved", "verdict": a, "reason": "r"},
            {"variant": "pinned git", "verdict": b, "reason": "s"}])[0]

    assert verdict("needs_attention", "verified") == "needs_attention"
    assert verdict("could_not_verify", "needs_attention") == "needs_attention"
    assert verdict("verified", "verified") == "verified"
    assert verdict("could_not_verify", "verified") == "could_not_verify"


def test_paired_final_keeps_both_in_reason():
    rec = {"verdict": "needs_attention", "reason": "4 new test(s) fail on the PR",
           "paired_dependency_runs": [{"variant": "pip-resolved", "verdict": "needs_attention", "reason": "112 fail"},
                                      {"variant": "pinned git", "companions": {"janitor-rs": "x"}}]}
    out = d.paired_final(rec)
    assert out["verdict"] == "needs_attention" and "pip-resolved run needs_attention" in out["reason"]
    assert "pinned git run: 4 new" in out["reason"]


def test_first_failure_from_cut_off_log():
    log = "....F\n___ test_x ___\nE   AttributeError: module 'janitor_rs' has no attribute 'conditional_join'\n"
    assert d.first_failure(log).startswith("AttributeError: module 'janitor_rs'")
    assert d.first_failure("all good") is None


def test_hypothesis_plugin_drops_shrink(tmp_path):
    pytest_hyp = __import__("importlib").util.find_spec("hypothesis")
    (tmp_path / f"{d.HYPOTHESIS_CAP_MODULE}.py").write_text(d.HYPOTHESIS_CAP_PLUGIN)
    (tmp_path / "test_h.py").write_text(
        "from hypothesis import settings, Phase\n"
        "def test_cap():\n    assert Phase.shrink not in settings.default.phases\n")
    if pytest_hyp is None:
        return
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", d.HYPOTHESIS_CAP_MODULE, str(tmp_path / "test_h.py"),
                        "-p", "no:cacheprovider"], cwd=tmp_path, capture_output=True, text=True,
                       env={"PYTHONPATH": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert r.returncode == 0, r.stdout + r.stderr
