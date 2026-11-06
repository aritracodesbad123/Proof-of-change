"""A shared test the base never runs is not a new pass. An empty base collection is not a new identity.

Both virtualenvs install pytest themselves. Nothing is borrowed through a path file. A pull-request-only
fixture is the only split. Probes are not changed: a cross-run id is a real base failure, not a claim name.
"""
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ops import daily_run as dr
from poc import probes

INI = "[pytest]\npython_files = *\npython_classes = *\npython_functions = *\n"
OLD = "def test_old():\n    assert True\n"
SHA = "09dbe1eec31ed1b3cd05366748865f11ba427d32"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _install_pytest(venv: Path) -> None:
    subprocess.run(["uv", "venv", str(venv), "--python", sys.executable], check=True, capture_output=True)
    # The runner always passes --timeout. That plugin is installed into each side, not borrowed
    # from the orchestrator's path.
    subprocess.run(["uv", "pip", "install", "-p", str(venv / "bin" / "python"), "pytest", "pytest-timeout"],
                   check=True, capture_output=True)


def _probe():
    """A differs claim whose observation never matches it. Settlement needs a real cross-run id."""
    body = {"id": "model-p1", "target": "o/r#1", "about": "x",
            "claims": [{"id": "C1", "text": "the score changes", "covers": ["gone.*"], "expect": "differs"}]}
    item = probes.entry(body, {"main": [{"out": 1}] * 3, "pr": [{"out": 1}] * 3}, None, [], "model", None)
    item["status"] = "ran"
    item["probe_changed_line_coverage"] = {"status": "measured", "changed_lines_total": 1,
                                            "changed_lines_covered": 1, "adequacy": "adequate"}
    return {"status": "ran", "items": [item]}


@pytest.fixture(scope="module")
def pythons(tmp_path_factory):
    if shutil.which("uv") is None:
        pytest.skip("uv is required to install pytest into a side virtualenv")
    work = tmp_path_factory.mktemp("venvs")
    base, pr = work / "venv-base", work / "venv-pr"
    _install_pytest(base)
    _install_pytest(pr)
    return {"main": base, "pr": pr}


def _run(tmp_path, pythons, main_checks: str, pr_checks: str, targets):
    from guardrails import sandbox

    work = tmp_path / "work"
    main, pr = work / "side-main", work / "side-pr"
    for root, checks, answer in ((main, main_checks, "1"), (pr, pr_checks, "2")):
        _write(root / "pytest.ini", INI)
        _write(root / "pkg" / "__init__.py", "")
        _write(root / "pkg" / "mod.py", f"def answer():\n    return {answer}\n")
        _write(root / "tests" / "__init__.py", "")
        _write(root / "tests" / "test_old.py", OLD)
        _write(root / "tests" / "checks.py", checks)
        _write(root / "tests" / "needs_relaxed.py", "import pytest_relaxed\n")
    _write(pr / "tests" / "conftest.py", "import pytest\n\n@pytest.fixture\ndef only_pr():\n    return 1\n")
    changed = ["pkg/mod.py", "tests/checks.py", "tests/needs_relaxed.py", "tests/conftest.py"]
    rec = {"files": {"all": changed, "package_py": ["pkg/mod.py"], "compiled": [], "other": changed[1:]},
           "base_ref": "2.2", "pr": {"tested_main_sha": SHA}}
    rundir = tmp_path / "run"
    rundir.mkdir()
    args = SimpleNamespace(runs=1, workers="0", test_timeout=60, run_timeout=180, build_timeout=60,
                           pr="https://example.test/pull/1", product_check=False, bench=None)
    was = sandbox.enabled()
    sandbox.configure(False)
    try:
        cmp, cnv, ex = dr.execute_tests(rec, pythons, targets, rundir, work, args,
                                        cwds={"main": main, "pr": pr})
    finally:
        sandbox.configure(was)
    return rec, cmp, cnv, ex, rundir


def test_shared_test_missing_on_the_base_is_not_a_new_pass(tmp_path, pythons):
    shared = ("import pytest\n\ndef test_shared(only_pr):\n    assert only_pr == 1\n\n"
              "@pytest.mark.skip(reason='held')\ndef test_held():\n    assert False\n")
    pr = shared + "\ndef test_new():\n    assert True\n"
    rec, cmp, cnv, ex, _rundir = _run(
        tmp_path, pythons, shared, pr,
        {"main": ["tests/test_old.py"], "pr": ["tests/test_old.py", "tests/checks.py"]})
    assert cnv is None and cmp is not None
    info = cmp["base_new_tests"]
    assert any(node.endswith("::test_shared") for node in info["shared_ids"])
    assert any("test_shared" in node for node in info["not_executed"])
    blob = " ".join(str(t) for t in cmp.get("new_tests_passing_ids") or [])
    blob += " ".join(str(t) for t in cmp.get("fixed") or [])
    assert "test_shared" not in blob and "test_held" not in blob
    assert "tests/needs_relaxed.py" in info["collection_failed"]
    dr._store_verdict(rec, cmp, cnv, ex)
    assert rec["verdict"] != "verified"
    assert "test_shared" in rec.get("collection_limitation", "")
    assert "tests/needs_relaxed.py" in rec["reason"]


def test_empty_base_collection_does_not_invent_new_tests(tmp_path, pythons):
    pr = "class Bucket_:\n    class nested:\n        def reports_names(self):\n            assert True\n"
    rec, cmp, cnv, ex, _rundir = _run(
        tmp_path, pythons, "# base file exists and has no tests\n", pr,
        {"main": ["tests/test_old.py"], "pr": ["tests/test_old.py", "tests/checks.py"]})
    assert cnv is None and cmp is not None
    info = cmp["base_new_tests"]
    assert "tests/checks.py" in info["discovery_empty"]
    assert not info["ids"]
    assert not any("reports_names" in str(t) for t in cmp.get("fixed") or [])
    assert not any("reports_names" in str(t) for t in cmp.get("new_tests_passing_ids") or [])
    assert dr.cross_run_test_ids(cmp, rec["files"]) == []
    dr._store_verdict(rec, cmp, cnv, ex)
    assert rec["verdict"] == "could_not_verify"
    assert rec.get("already_on_base") is None


def test_nested_fixed_id_is_a_real_base_failure_and_does_not_prove_without_one(tmp_path, pythons):
    base = "class Bucket_:\n    class nested:\n        def old_case(self):\n            assert True\n"
    pr = base + """
        def reports_names(self):
            from pkg.mod import answer
            assert answer() == 2
"""
    rec, cmp, cnv, ex, rundir = _run(
        tmp_path, pythons, base, pr,
        {"main": ["tests/test_old.py"], "pr": ["tests/test_old.py"]})
    assert cnv is None and cmp is not None
    ids = dr.cross_run_test_ids(cmp, rec["files"])
    assert ids and all("reports_names" in node for node in ids)
    junit = (rundir / "junit-main-1.xml").read_text()
    assert "reports_names" in junit and "failure" in junit
    assert not any("needs_relaxed" in node for node in ids)
    _v, reason, fl = dr.verdict_for(cmp, None, None, rec["files"], _probe())
    assert "cross_run_settled" in fl and ids[0] in reason and "as proven" in reason

    blocked = dict(cmp)
    blocked["fixed"] = []
    blocked["base_new_tests"] = dict(cmp["base_new_tests"], ids=[], failed_on_base=[],
                                     collection_failed=["tests/needs_relaxed.py"])
    assert dr.cross_run_test_ids(blocked, rec["files"]) == []
    _bv, breason, bfl = dr.verdict_for(blocked, None, None, rec["files"], _probe())
    assert "cross_run_settled" not in bfl and "as proven" not in breason
