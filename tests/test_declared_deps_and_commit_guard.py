"""Declared test requirements and the wrong-commit guard (2026-10-14 decision)."""
import json
import subprocess

from ops import daily_run as d

PANDERA_LIKE = """
[project]
name = "pkg"
optional-dependencies = {pandas = ["numpy >= 1.24", "pandas >= 2.1"], io = ["zarr>=3.0", "fsspec"], all = ["pkg[io]"]}
[dependency-groups]
testing = ["pytest", "pytest-cov", "pytest-asyncio", "--index-url=http://evil"]
dev = ["pkg[all]", "pytest-mypy-plugins"]
"""


def test_declared_test_deps(tmp_path):
    (tmp_path / "pyproject.toml").write_text(PANDERA_LIKE)
    got = d.declared_test_deps(tmp_path, ["tests/pandas/test_checks.py"], "pkg")
    assert got == ["pytest-asyncio", "numpy >= 1.24", "pandas >= 2.1"]
    got = d.declared_test_deps(tmp_path, ["pkg/tests/backends/test_zarr.py"], "pkg")
    assert got == ["pytest-asyncio", "zarr>=3.0"]
    assert not any(r.startswith("-") or r.startswith("pkg") for r in got)


def test_no_pyproject_means_nothing(tmp_path):
    assert d.declared_test_deps(tmp_path, ["tests/test_a.py"], "pkg") == []


def _venv_with(tmp_path, dist, du):
    sp = tmp_path / "venv" / "lib" / "python3.12" / "site-packages" / f"{dist}-1.0.dist-info"
    sp.mkdir(parents=True)
    if du is not None:
        (sp / "direct_url.json").write_text(json.dumps(du))
    return tmp_path / "venv"


def test_vcs_commit_must_match(tmp_path):
    v = _venv_with(tmp_path, "janitor_rs", {"url": "https://x/y.git", "vcs_info": {"vcs": "git", "commit_id": "5449683" + "0" * 33}})
    assert d.check_installed_commit(v, "janitor-rs", "5449683")[0]
    ok, info = d.check_installed_commit(v, "janitor-rs", "abcdef1234")
    assert not ok and "not the requested" in info["why"]


def test_missing_direct_url_fails_closed(tmp_path):
    v = _venv_with(tmp_path, "pkg", None)
    ok, info = d.check_installed_commit(v, "pkg", "a" * 40)
    assert not ok and "cannot be checked" in info["why"]


def test_local_checkout_must_be_at_requested_commit(tmp_path):
    co = tmp_path / "side-pr"
    co.mkdir()
    git = ["git", "-C", str(co), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", str(co)], check=True)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "x"], check=True)
    head = subprocess.run(["git", "-C", str(co), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    v = _venv_with(tmp_path, "pkg", {"url": co.resolve().as_uri(), "dir_info": {"editable": True}})
    assert d.check_installed_commit(v, "pkg", head, co)[0]
    ok, info = d.check_installed_commit(v, "pkg", "b" * 40, co)
    assert not ok and "not the requested" in info["why"]
    other = tmp_path / "elsewhere"
    other.mkdir()
    ok, info = d.check_installed_commit(v, "pkg", head, other)
    assert not ok and "not from the checked-out side" in info["why"]


def test_declared_project_name_reads_project_table_only(tmp_path):
    assert d.declared_project_name(tmp_path) is None
    (tmp_path / "pyproject.toml").write_text("not toml")
    assert d.declared_project_name(tmp_path) is None
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "  zarr  "\n')
    assert d.declared_project_name(tmp_path) == "zarr"
    (tmp_path / "pyproject.toml").write_text('[tool.poetry]\nname = "zarr"\n')
    assert d.declared_project_name(tmp_path) is None


def test_declared_project_name_is_used_when_label_differs(tmp_path):
    co = tmp_path / "side-main"
    co.mkdir()
    subprocess.run(["git", "init", "-q", str(co)], check=True)
    subprocess.run(["git", "-C", str(co), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                    "--allow-empty", "-m", "x"], check=True)
    head = subprocess.run(["git", "-C", str(co), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (co / "pyproject.toml").write_text('[project]\nname = "zarr"\n')
    v = _venv_with(tmp_path, "zarr", {"url": co.resolve().as_uri(), "dir_info": {"editable": True}})
    ok, info = d.check_installed_commit(v, "zarr-python", head, co)
    assert ok and info["dist"] == "zarr" and info["installed"] == head
    bad, bad_info = d.check_installed_commit(v, "zarr-python", "f" * 40, co)
    assert not bad and bad_info["dist"] == "zarr" and "not the requested" in bad_info["why"]


def test_declared_name_rejects_another_directory(tmp_path):
    co = tmp_path / "side-main"
    co.mkdir()
    (co / "pyproject.toml").write_text('[project]\nname = "zarr"\n')
    other = tmp_path / "elsewhere"
    other.mkdir()
    v = _venv_with(tmp_path, "zarr", {"url": other.resolve().as_uri(), "dir_info": {"editable": True}})
    ok, info = d.check_installed_commit(v, "zarr-python", "a" * 40, co)
    assert not ok and info["dist"] == "zarr" and "not from the checked-out side" in info["why"]


def test_declared_name_does_not_rescue_a_missing_install(tmp_path):
    co = tmp_path / "side-main"
    co.mkdir()
    (co / "pyproject.toml").write_text('[project]\nname = "zarr"\n')
    v = _venv_with(tmp_path, "other", {"url": "https://x/y.git", "vcs_info": {"vcs": "git", "commit_id": "a" * 40}})
    ok, info = d.check_installed_commit(v, "zarr-python", "a" * 40, co)
    assert not ok and info["dist"] == "zarr-python" and "no direct_url.json" in info["why"]


def test_installed_label_without_direct_url_is_not_replaced(tmp_path):
    co = tmp_path / "side-main"
    co.mkdir()
    subprocess.run(["git", "init", "-q", str(co)], check=True)
    subprocess.run(["git", "-C", str(co), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                    "--allow-empty", "-m", "x"], check=True)
    head = subprocess.run(["git", "-C", str(co), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (co / "pyproject.toml").write_text('[project]\nname = "zarr"\n')
    v = _venv_with(tmp_path, "zarr-python", None)
    sp = v / "lib" / "python3.12" / "site-packages" / "zarr-1.0.dist-info"
    sp.mkdir()
    (sp / "direct_url.json").write_text(json.dumps({"url": co.resolve().as_uri(), "dir_info": {"editable": True}}))
    ok, info = d.check_installed_commit(v, "zarr-python", head, co)
    assert not ok and info["dist"] == "zarr-python" and "no direct_url.json" in info["why"]
