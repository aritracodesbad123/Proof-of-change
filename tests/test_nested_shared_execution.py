"""Changed nested tests run on the base even when the node id already existed.

A strengthened assertion is a real base failure. An import of a helper that exists only on the
pull request is not that failure, and it is not a new pass. Both sides install pytest themselves.
"""
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ops import daily_run as dr

INI = "[pytest]\npython_files = *\npython_classes = *\npython_functions = *\n"
OLD = "def test_old():\n    assert True\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _install(venv: Path) -> None:
    subprocess.run(["uv", "venv", str(venv), "--python", sys.executable], check=True, capture_output=True)
    subprocess.run(["uv", "pip", "install", "-p", str(venv / "bin" / "python"), "pytest", "pytest-timeout"],
                   check=True, capture_output=True)


@pytest.fixture(scope="module")
def pythons(tmp_path_factory):
    if shutil.which("uv") is None:
        pytest.skip("uv is required to install pytest into a side virtualenv")
    work = tmp_path_factory.mktemp("venvs")
    base, pr = work / "venv-base", work / "venv-pr"
    _install(base)
    _install(pr)
    return {"main": base, "pr": pr}


def _execute(tmp_path, pythons, base_checks: str, pr_checks: str, extra_pr: dict | None = None,
             files_all: list[str] | None = None, base_mod: str | None = None, pr_mod: str | None = None):
    from guardrails import sandbox

    work = tmp_path / "work"
    main, pr = work / "side-main", work / "side-pr"
    mods = {main: base_mod or "def answer():\n    return 1\n", pr: pr_mod or "def answer():\n    return 2\n"}
    for root, checks in ((main, base_checks), (pr, pr_checks)):
        _write(root / "pytest.ini", INI)
        _write(root / "pkg" / "__init__.py", "")
        _write(root / "pkg" / "mod.py", mods[root])
        _write(root / "tests" / "__init__.py", "")
        _write(root / "tests" / "test_old.py", OLD)
        _write(root / "tests" / "checks.py", checks)
    for rel, text in (extra_pr or {}).items():
        _write(pr / rel, text)
    changed = files_all or ["pkg/mod.py", "tests/checks.py"]
    rec = {"files": {"all": changed, "package_py": ["pkg/mod.py"], "compiled": [],
                     "other": [item for item in changed if item != "pkg/mod.py"]},
           "base_ref": "main"}
    rundir = tmp_path / "run"
    rundir.mkdir()
    args = SimpleNamespace(runs=1, workers="0", test_timeout=60, run_timeout=180, build_timeout=60,
                           pr="https://example.test/pull/1", product_check=False, bench=None)
    was = sandbox.enabled()
    sandbox.configure(False)
    try:
        # Both sides already run the nested file in the ordinary selection. The cross-run still has
        # to execute the shared id with the pull-request body on the base, or the strengthened
        # assertion is invisible and the result stays a plain pass.
        both = ["tests/test_old.py", "tests/checks.py"]
        cmp, cnv, ex = dr.execute_tests(
            rec, pythons, {"main": both, "pr": both},
            rundir, work, args, cwds={"main": main, "pr": pr})
    finally:
        sandbox.configure(was)
    return rec, cmp, cnv, ex, rundir


BASE_NESTED = """
class Bucket_:
    class nested:
        def old_case(self):
            assert True
"""

PR_NESTED = """
class Bucket_:
    class nested:
        def old_case(self):
            from pkg.mod import answer
            assert answer() == 2
"""


def test_shared_nested_body_is_a_real_base_failure(tmp_path, pythons):
    """The same node id with a stronger assertion fails on the base and is the cross-run id."""
    rec, cmp, cnv, _ex, rundir = _execute(tmp_path, pythons, BASE_NESTED, PR_NESTED)
    assert cnv is None and cmp is not None
    assert any("old_case" in str(t) for t in cmp["fixed"])
    # The shared id is ordinary fixed evidence. It is not eligible to settle a differs claim.
    assert dr.cross_run_test_ids(cmp, rec["files"]) == []
    junit = (rundir / "junit-main-1.xml").read_text()
    assert "old_case" in junit and "failure" in junit
    assert not any("old_case" in str(t) for t in cmp.get("new_tests_passing_ids") or [])


HELPER = """
class Bucket_:
    class nested:
        def old_case(self):
            from pkg.helper_util import value
            assert value == 1
"""


def test_type_error_on_the_base_can_still_be_a_fix(tmp_path, pythons):
    """A TypeError from the call under test is not treated as a missing import."""
    body = """
class Bucket_:
    class nested:
        def old_case(self):
            from pkg.mod import answer
            assert answer(2) == 2
"""
    rec, cmp, cnv, _ex, _rundir = _execute(
        tmp_path, pythons, body, body,
        base_mod="def answer():\n    return 1\n",
        pr_mod="def answer(n):\n    return n\n")
    assert cnv is None and cmp is not None
    info = cmp["base_new_tests"]
    named = " ".join(info.get("environment_limits") or [])
    assert "could not import" not in named
    assert any("old_case" in str(t) for t in cmp["fixed"])
    assert dr.cross_run_test_ids(cmp, rec["files"]) == []


def test_missing_base_helper_is_not_a_fix_and_not_a_new_pass(tmp_path, pythons):
    """Importing a helper that exists only on the pull request does not prove a fix."""
    rec, cmp, cnv, ex, _rundir = _execute(
        tmp_path, pythons, HELPER, HELPER,
        extra_pr={"pkg/helper_util.py": "value = 1\n"},
        files_all=["pkg/mod.py", "pkg/helper_util.py", "tests/checks.py"])
    assert cnv is None and cmp is not None
    blob = " ".join(str(t) for t in (cmp.get("fixed") or []) + (cmp.get("new_tests_passing_ids") or []))
    assert "old_case" not in blob
    info = cmp["base_new_tests"]
    named = " ".join(info.get("not_executed") or []) + " ".join(info.get("environment_limits") or [])
    assert "old_case" in named and "helper_util" in named
    assert dr.cross_run_test_ids(cmp, rec["files"]) == []
    dr._store_verdict(rec, cmp, cnv, ex)
    assert rec["verdict"] == "could_not_verify"
    assert "helper_util" in rec.get("collection_limitation", "")
    assert rec.get("already_on_base") is None
