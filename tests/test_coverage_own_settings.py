"""Coverage gate runs with its own coverage settings: a project's coverage include plus our --cov source no longer
trips the project's filterwarnings = error, and the project's own warnings are still errors."""
import json
import subprocess
import sys
import textwrap

import pytest

from ops import daily_run as dr

pytest.importorskip("pytest_cov")


def _project(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "m.py").write_text("def f():\n    return 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_m.py").write_text(textwrap.dedent("""
        import warnings
        from pkg.m import f
        def test_f():
            assert f() == 1
        def test_project_warnings_are_still_errors():
            try:
                warnings.warn("project warning")
            except UserWarning:
                return
            raise AssertionError("project filterwarnings no longer turn warnings into errors")
    """))
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\nfilterwarnings = ["error"]\n'
                                             'pythonpath = ["."]\n[tool.coverage.run]\ninclude = ["pkg/*"]\n')


def _pytest(tmp_path, *extra):
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "no:xdist", "tests",
                           f"--cov={tmp_path / 'pkg'}", f"--cov-report=json:{tmp_path / 'c.json'}", *extra],
                          cwd=tmp_path, capture_output=True, text=True)


def test_project_include_plus_our_source_fails_without_own_settings(tmp_path):
    _project(tmp_path)
    r = _pytest(tmp_path)
    assert "include-ignored" in r.stdout + r.stderr and not (tmp_path / "c.json").exists()


def test_own_settings_measure_and_keep_project_warnings(tmp_path):
    _project(tmp_path)
    (tmp_path / "rc").write_text(dr.COVERAGE_RC)
    r = _pytest(tmp_path, f"--cov-config={tmp_path / 'rc'}")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "2 passed" in r.stdout
    assert "pkg/m.py" in json.loads((tmp_path / "c.json").read_text())["files"]


def test_settings_only_turn_off_coverage_warnings():
    lines = [ln.strip() for ln in dr.COVERAGE_RC.splitlines()]
    assert lines[0] == "[run]" and "disable_warnings =" in lines
    assert not any(k in dr.COVERAGE_RC for k in ("filterwarnings", "-W", "include =", "source ="))
    assert "warning filters are unchanged" in dr.COVERAGE_RC_NOTE
