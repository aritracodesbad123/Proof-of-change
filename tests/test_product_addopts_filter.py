"""Product checks keep the project's pytest addopts but strip, by flag name, only the flags our command sets."""
import subprocess
import sys
from pathlib import Path

from ops import daily_run as dr
from poc import pytest_addopts as pa


def test_pytester_plugin_kept_cov_and_workers_stripped(tmp_path):
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\naddopts = -p pytester --cov=pkg --cov-report term -n 4 --dist loadfile -rfE -vv --tb=short\n")
    assert pa.find_addopts(tmp_path)[0] == "pytest.ini"
    assert dr.repo_addopts_args(True, tmp_path) == ["-o", "addopts=-p pytester"]
    assert dr.repo_addopts_flag(True, tmp_path) == "-o 'addopts=-p pytester' "


def test_equals_forms_and_joined_short_forms():
    kept, removed = pa.strip_overridden(
        ["-p", "xdist", "--numprocesses=auto", "--dist=load", "--junitxml=out.xml", "--junit-xml", "o.xml",
         "--cov", "src", "--cov", "--cov-branch", "--cov-fail-under=90", "--timeout=30", "--color=yes",
         "-n4", "-ra", "-q", "--strict-markers", "-o", "junit_family=xunit1", "--override-ini=junit_family=legacy",
         "-o", "xfail_strict=true", "--import-mode=importlib"])
    assert kept == ["-p", "xdist", "--strict-markers", "-o", "xfail_strict=true", "--import-mode=importlib"]
    assert "--numprocesses=auto" in removed and "-n4" in removed and "src" in removed


def test_cov_without_value_does_not_eat_next_flag():
    assert pa.strip_overridden(["--cov", "-p", "pytester"])[0] == ["-p", "pytester"]


def test_no_config_at_all(tmp_path):
    assert pa.find_addopts(tmp_path) == (None, [])
    assert dr.repo_addopts_args(True, tmp_path) == []
    assert dr.repo_addopts_flag(True, tmp_path) == ""
    assert dr.repo_addopts_args(True, None) == []


def test_nothing_to_strip_passes_nothing(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\naddopts = ["-p", "pytester", "-ra"]\n')
    assert dr.repo_addopts_args(True, tmp_path) == ["-o", "addopts=-p pytester"]
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\naddopts = "-p pytester"\n')
    assert dr.repo_addopts_args(True, tmp_path) == []


def test_config_file_order_follows_pytest(tmp_path):
    (tmp_path / "setup.cfg").write_text("[tool:pytest]\naddopts = --cov=a\n")
    assert pa.find_addopts(tmp_path) == ("setup.cfg", ["--cov=a"])
    (tmp_path / "tox.ini").write_text("[pytest]\naddopts = -n 2\n")
    assert pa.find_addopts(tmp_path)[0] == "tox.ini"
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")  # no pytest table: skipped
    assert pa.find_addopts(tmp_path)[0] == "tox.ini"
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\naddopts = '-q'\n")
    assert pa.find_addopts(tmp_path) == ("pyproject.toml", ["-q"])
    (tmp_path / "pytest.ini").write_text("[other]\n")  # pytest.ini wins even without a [pytest] section
    assert pa.find_addopts(tmp_path) == ("pytest.ini", [])


def test_study_route_unchanged(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = -p pytester --cov=x\n")
    assert dr.repo_addopts_args(False, tmp_path) == ["-o", "addopts="]
    assert dr.repo_addopts_flag(False, tmp_path) == "-o addopts= "


def test_filtered_override_really_loads_pytester(tmp_path):
    """End to end with real pytest: the repo's -p pytester survives, a stripped flag pytest could not parse is gone."""
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = -p pytester --cov-made-up-flag=1\n"
                                         "pytester_example_dir = .\n")
    (tmp_path / "test_x.py").write_text("def test_x(pytester):\n    assert pytester\n")
    args = dr.repo_addopts_args(True, tmp_path)
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args, "test_x.py"],
                       cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
