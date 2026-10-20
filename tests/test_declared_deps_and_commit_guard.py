"""Declared test requirements and the wrong-commit guard (2026-10-14 decision)."""
import json
import subprocess
from pathlib import Path

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


def _git_checkout(path):
    path.mkdir(parents=True, exist_ok=True)
    git = ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "x"], check=True)
    return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()


def _pointing_at(tmp_path, dist, checkout, **extra):
    body = {"url": Path(checkout).resolve().as_uri(), "dir_info": {"editable": True}}
    body.update(extra)
    return _venv_with(tmp_path, dist, body)


def test_name_guard_matches_a_normalized_vcs_commit(tmp_path):
    """The previous guard looks up a name. A dry run can still select it."""
    v = _venv_with(tmp_path, "janitor_rs", {"url": "https://x/y.git", "vcs_info": {"vcs": "git", "commit_id": "5449683" + "0" * 33}})
    assert d.check_installed_commit_by_name(v, "janitor-rs", "5449683")[0]
    ok, info = d.check_installed_commit_by_name(v, "janitor-rs", "abcdef1234")
    assert not ok and "not the requested" in info["why"] and info["dist"] == "janitor-rs"


def test_name_guard_misses_a_distribution_installed_under_another_name(tmp_path):
    co = tmp_path / "side-main"
    head = _git_checkout(co)
    (co / "pyproject.toml").write_text('[project]\nname = "zarr"\n')
    v = _pointing_at(tmp_path, "zarr", co)
    ok, info = d.check_installed_commit_by_name(v, "zarr-python", head, co)
    assert not ok and info["dist"] == "zarr-python" and "no direct_url.json" in info["why"]
    found, found_info = d.check_installed_commit(v, "zarr-python", head, co)
    assert found and found_info["dist"] == "zarr" and found_info["installed"] == head


def test_missing_direct_url_fails_closed(tmp_path):
    co = tmp_path / "side-main"
    head = _git_checkout(co)
    v = _venv_with(tmp_path, "pkg", None)
    ok, info = d.check_installed_commit(v, "pkg", head, co)
    assert not ok and info["dist"] is None and "cannot be checked" in info["why"]
    missing_checkout, missing_info = d.check_installed_commit(v, "pkg", "a" * 40)
    assert not missing_checkout and "cannot be checked" in missing_info["why"]


def test_local_checkout_must_be_at_requested_commit(tmp_path):
    co = tmp_path / "side-pr"
    head = _git_checkout(co)
    v = _pointing_at(tmp_path, "pkg", co)
    assert d.check_installed_commit(v, "pkg", head, co)[0]
    ok, info = d.check_installed_commit(v, "pkg", "b" * 40, co)
    assert not ok and info["dist"] == "pkg" and "not the requested" in info["why"]
    other = tmp_path / "elsewhere"
    other.mkdir()
    ok, info = d.check_installed_commit(v, "pkg", head, other)
    assert not ok and info["dist"] == "pkg" and "not from the checked-out side" in info["why"]


def test_pyproject_name_differs_from_the_repo_label(tmp_path):
    """zarr-python installs as zarr. The guard records zarr because that install names the checkout."""
    co = tmp_path / "side-main"
    head = _git_checkout(co)
    (co / "pyproject.toml").write_text('[project]\nname = "zarr"\n')
    v = _pointing_at(tmp_path, "zarr", co)
    ok, info = d.check_installed_commit(v, "zarr-python", head, co)
    assert ok and info["dist"] == "zarr" and info["installed"] == head
    bad, bad_info = d.check_installed_commit(v, "zarr-python", "f" * 40, co)
    assert not bad and bad_info["dist"] == "zarr" and "not the requested" in bad_info["why"]


def test_setup_py_name_differs_from_the_repo_label(tmp_path):
    """sentry-python installs as sentry-sdk, and the name is only in setup.py."""
    co = tmp_path / "side-pr"
    head = _git_checkout(co)
    (co / "setup.py").write_text('from setuptools import setup\nsetup(name="sentry-sdk")\n')
    v = _pointing_at(tmp_path, "sentry-sdk", co)
    ok, info = d.check_installed_commit(v, "sentry-python", head, co)
    assert ok and info["dist"] == "sentry-sdk" and info["installed"] == head


def test_setup_cfg_name_differs_from_the_repo_label(tmp_path):
    co = tmp_path / "side-main"
    head = _git_checkout(co)
    (co / "setup.cfg").write_text("[metadata]\nname = cfg-dist\n")
    v = _pointing_at(tmp_path, "cfg-dist", co)
    ok, info = d.check_installed_commit(v, "cfg-repo", head, co)
    assert ok and info["dist"] == "cfg-dist"


def test_poetry_name_differs_from_the_repo_label(tmp_path):
    co = tmp_path / "side-main"
    head = _git_checkout(co)
    (co / "pyproject.toml").write_text('[tool.poetry]\nname = "olive-ai"\n')
    v = _pointing_at(tmp_path, "olive-ai", co)
    ok, info = d.check_installed_commit(v, "olive", head, co)
    assert ok and info["dist"] == "olive-ai" and info["installed"] == head


def test_declared_name_is_not_what_gets_checked(tmp_path):
    """A name written in the checkout is not a match. The install that names the folder is."""
    co = tmp_path / "side-main"
    head = _git_checkout(co)
    (co / "pyproject.toml").write_text('[project]\nname = "not-installed"\n[tool.poetry]\nname = "also-not"\n')
    (co / "setup.py").write_text('setup(name="still-not")\n')
    (co / "setup.cfg").write_text("[metadata]\nname = no-match\n")
    v = _pointing_at(tmp_path, "actual-dist", co)
    ok, info = d.check_installed_commit(v, "repo-label", head, co)
    assert ok and info["dist"] == "actual-dist"


def test_zero_distributions_point_at_the_checkout(tmp_path):
    co = tmp_path / "side-main"
    head = _git_checkout(co)
    v = _venv_with(tmp_path, "zarr", {"url": "https://pypi.org/simple/zarr", "archive_info": {}})
    ok, info = d.check_installed_commit(v, "zarr-python", head, co)
    assert not ok and info["dist"] is None and "cannot be checked" in info["why"]


def test_two_distributions_point_at_the_same_folder(tmp_path):
    co = tmp_path / "side-main"
    head = _git_checkout(co)
    v = _pointing_at(tmp_path, "zarr", co)
    extra = v / "lib" / "python3.12" / "site-packages" / "sb3-contrib-2.0.dist-info"
    extra.mkdir()
    recorded = v / "lib" / "python3.12" / "site-packages" / "zarr-1.0.dist-info" / "direct_url.json"
    (extra / "direct_url.json").write_text(recorded.read_text())
    ok, info = d.check_installed_commit(v, "zarr-python", head, co)
    assert not ok and "more than one" in info["why"]
    assert set(info["dist"].split(", ")) == {"sb3-contrib", "zarr"}


def test_install_from_another_folder_fails(tmp_path):
    co = tmp_path / "side-main"
    _git_checkout(co)
    other = tmp_path / "elsewhere"
    other.mkdir()
    v = _venv_with(tmp_path, "zarr", {"url": other.resolve().as_uri(), "dir_info": {"editable": True}})
    ok, info = d.check_installed_commit(v, "zarr-python", "a" * 40, co)
    assert not ok and info["dist"] == "zarr" and "not from the checked-out side" in info["why"]
    assert str(other.resolve()) in info["why"] or other.resolve().as_uri() in info["why"]


def test_vcs_commit_must_match_when_the_record_names_one(tmp_path):
    co = tmp_path / "side-pr"
    head = _git_checkout(co)
    v = _pointing_at(tmp_path, "pkg", co, vcs_info={"vcs": "git", "commit_id": head})
    assert d.check_installed_commit(v, "repo-label", head[:12], co)[0]
    recorded = v / "lib" / "python3.12" / "site-packages" / "pkg-1.0.dist-info" / "direct_url.json"
    recorded.write_text(json.dumps({"url": co.resolve().as_uri(), "dir_info": {"editable": True},
                                    "vcs_info": {"vcs": "git", "commit_id": "b" * 40}}))
    ok, info = d.check_installed_commit(v, "repo-label", head, co)
    assert not ok and info["dist"] == "pkg" and "installed from commit" in info["why"] and "not the requested" in info["why"]


def test_file_url_matches_by_realpath(tmp_path):
    """A percent-encoded file URL and a symlink to the checkout are the same folder."""
    real = tmp_path / "side main"
    head = _git_checkout(real)
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    assert "%20" in real.as_uri()
    v = _venv_with(tmp_path, "zarr", {"url": real.as_uri(), "dir_info": {"editable": True}})
    ok, info = d.check_installed_commit(v, "zarr-python", head, link)
    assert ok and info["dist"] == "zarr"
