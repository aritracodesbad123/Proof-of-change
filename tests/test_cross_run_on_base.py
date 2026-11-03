"""The daily run executes the pull request's new or edited tests on the base tree.

A test that fails there and passes on the pull request is stored where the narrow cross-run rule reads it.
A test that fails to import on the base is not a cross-run and is not stored as a pass. The dask and rich
fixtures stay not verified. Nothing here contacts GitHub.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from ops import daily_run as dr
from poc import probes

COV = {"status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1, "adequacy": "adequate"}


def test_changed_test_files_follow_default_python_files():
    """pytest's default python_files patterns, and not helpers or source files."""
    files = {
        "all": [
            "pkg/mod.py",
            "tests/test_a.py",
            "tests/a_test.py",
            "tests/helper.py",
            "tests/conftest.py",
            "tests/check_a.py",
            "../tests/test_escape.py",
        ]
    }
    assert dr.changed_test_files(files) == ["tests/a_test.py", "tests/test_a.py"]


def test_an_import_error_on_the_base_is_not_stored_as_a_failure_or_a_pass(tmp_path):
    rels = ["tests/test_mod.py", "tests/test_helper.py"]
    base = [
        {
            "tests.test_mod::test_answer": ("failed", "AssertionError: assert 1 == 2"),
            "tests.test_helper::test_helper": ("error", "ImportError: No module named 'only_on_pr'"),
            "tests.test_mod::test_already": ("passed", ""),
        }
    ]
    pr = [
        {
            "tests.test_mod::test_answer": ("passed", ""),
            "tests.test_helper::test_helper": ("passed", ""),
            "tests.test_mod::test_already": ("passed", ""),
        }
    ]
    results = {"main": [{}], "pr": [dict(pr[0])]}
    files = {"all": ["pkg/mod.py", "tests/test_mod.py", "tests/helper.py"], "package_py": ["pkg/mod.py"]}
    dr._fold_cross_run(results, base, None, rels, tmp_path, files)
    assert results["main"][0]["tests.test_mod::test_answer"] == ("failed", "AssertionError: assert 1 == 2")
    assert "tests.test_helper::test_helper" not in results["main"][0]
    assert "tests.test_mod::test_already" not in results["main"][0]
    cmp = dr.compare_sides(results)
    ids = dr.cross_run_test_ids(cmp, files)
    assert any(i.endswith("test_answer") for i in ids)
    assert cmp["base_messages"]["tests.test_mod::test_answer"] == "AssertionError: assert 1 == 2"
    assert not any("test_helper" in i for i in ids)
    assert any(i.endswith("test_helper") for i in cmp["new_tests_passing_ids"])


def test_base_failure_fixtures_keep_an_assertion_and_drop_a_missing_helper(tmp_path):
    root = Path(__file__).resolve().parent / "fixtures" / "cross_run_base"
    seen = set()
    for path in sorted(root.glob("*.json")):
        spec = json.loads(path.read_text())
        seen.add(path.name)
        files = {"all": spec["files"], "package_py": spec.get("package_py") or []}
        body = spec.get("traceback") or ""
        note = dr._base_failure_note(spec["message"], body)
        assert dr._base_failure_counts(spec["outcome"], note, body, files) is spec["counts"], path.name
        tid = spec["test"]
        results = {"main": [{}], "pr": [{tid: ("passed", "")}]}
        dr._fold_cross_run(results, [{tid: (spec["outcome"], spec["message"], body)}], None,
                           [spec["test_file"]], tmp_path, files)
        cmp = dr.compare_sides(results)
        if spec["counts"]:
            assert note == spec["stored"]
            assert "\n" not in note
            assert tid in cmp["fixed"]
            assert cmp["base_messages"][tid] == spec["stored"]
            assert dr.cross_run_test_ids(cmp, files) == [tid]
        else:
            assert tid not in results["main"][0]
            assert tid not in cmp["fixed"]
            assert tid not in (cmp.get("base_messages") or {})
            assert dr.cross_run_test_ids(cmp, files) == []
    assert seen == {"assertion.json", "missing-helper.json"}


def test_an_exception_in_changed_code_counts_and_one_in_support_does_not():
    files = {"all": ["pkg/mod.py", "tests/test_mod.py", "tests/helper.py", "tests/conftest.py"],
             "package_py": ["pkg/mod.py"]}
    raised = "pkg/mod.py:4: in answer\n    raise ValueError('nope')\nE   ValueError: nope"
    assert dr._base_failure_counts("failed", "ValueError: nope", raised, files)
    assert dr._base_failure_note("ValueError: nope\nmore", raised) == "ValueError: nope"
    ended = "tests/helper.py:2: in setup\n    raise ValueError('nope')\nE   ValueError: nope"
    assert not dr._base_failure_counts("error", "ValueError: nope", ended, files)
    attr = "E   AttributeError: module 'tests.conftest' has no attribute 'fix'"
    assert not dr._base_failure_counts("error", "AttributeError: module 'tests.conftest' has no attribute 'fix'",
                                       attr, files)


def _agreed_differs():
    raw = {
        "id": "model-p1",
        "claims": [{"id": "C1", "text": "the returned value changes", "covers": ["out"], "expect": "differs"}],
        "main": {"out": 1},
        "pr": {"out": 1},
    }
    body = {"id": raw["id"], "target": "o/r#1", "about": "x", "claims": raw["claims"]}
    item = probes.entry(body, {"main": [raw["main"]] * 3, "pr": [raw["pr"]] * 3}, None, [], "model", None)
    item["status"] = "ran"
    item["probe_changed_line_coverage"] = dict(COV)
    return {"status": "ran", "items": [item]}


def _venv(work: Path, name: str) -> Path:
    """A side interpreter that can import pytest under the run's own HOME.

    The daily run gives each side a fresh HOME, so a user-site install is not on the path. This venv
    points at the pytest the test runner already has."""
    import pytest

    venv = work / name
    bindir = venv / "bin"
    bindir.mkdir(parents=True)
    (bindir / "python").symlink_to(sys.executable)
    ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    sp = venv / "lib" / ver / "site-packages"
    sp.mkdir(parents=True)
    (sp / "runner.pth").write_text(str(Path(pytest.__file__).resolve().parent.parent) + "\n")
    (venv / "pyvenv.cfg").write_text(
        f"home = {Path(sys.executable).resolve().parent}\ninclude-system-site-packages = false\n"
        f"version = {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\n"
    )
    return venv


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _project(root: Path, answer: str, with_new_tests: bool) -> None:
    _write(root / "pytest.ini", "[pytest]\n")
    _write(root / "pkg" / "__init__.py", "")
    _write(root / "pkg" / "mod.py", f"def answer():\n    return {answer}\n")
    _write(root / "tests" / "test_old.py", "def test_old():\n    assert True\n")
    if not with_new_tests:
        return
    _write(root / "tests" / "test_mod.py", "from pkg.mod import answer\n\ndef test_answer():\n    assert answer() == 2\n")
    _write(root / "tests" / "helper.py", "OK = True\n")
    _write(root / "tests" / "test_helper.py", "import tests.helper as helper\n\ndef test_helper():\n    assert helper.OK\n")


def test_a_fake_pr_stores_the_cross_run_and_an_import_error_does_not_count(tmp_path):
    """The daily-run command runs the pull request's tests on the base tree and stores the pair."""
    import pytest

    pytest.importorskip("pytest_timeout")
    from guardrails import sandbox

    work = tmp_path / "work"
    main, pr = work / "side-main", work / "side-pr"
    _project(main, "1", with_new_tests=False)
    _project(pr, "2", with_new_tests=True)
    venvs = {"main": _venv(work, "venv-main"), "pr": _venv(work, "venv-pr")}
    files = {
        "all": ["pkg/mod.py", "tests/test_mod.py", "tests/test_helper.py", "tests/helper.py"],
        "package_py": ["pkg/mod.py"],
        "compiled": [],
        "other": ["tests/test_mod.py", "tests/test_helper.py", "tests/helper.py"],
    }
    rec = {"files": files}
    (tmp_path / "run").mkdir()
    targets = {"main": ["tests/test_old.py"], "pr": ["tests/test_old.py", "tests/test_mod.py", "tests/test_helper.py"]}
    a = SimpleNamespace(
        runs=1,
        workers="0",
        test_timeout=60,
        run_timeout=120,
        build_timeout=60,
        pr="https://github.com/o/r/pull/1",
        product_check=False,
        bench=None,
    )
    was = sandbox.enabled()
    sandbox.configure(False)
    try:
        cmp, cnv, _ex = dr.execute_tests(rec, venvs, targets, tmp_path / "run", work, a, cwds={"main": main, "pr": pr})
    finally:
        sandbox.configure(was)
    assert cnv is None and cmp is not None
    assert not (main / "tests" / "test_mod.py").exists()
    assert not (main / "tests" / "test_helper.py").exists()
    assert not (main / "tests" / "helper.py").exists()
    assert "return 1" in (main / "pkg" / "mod.py").read_text()
    ids = dr.cross_run_test_ids(cmp, files)
    assert any(i.endswith("test_answer") for i in ids)
    answer = next(i for i in ids if i.endswith("test_answer"))
    stored = cmp["base_messages"][answer]
    assert stored.startswith("AssertionError") and "\n" not in stored
    assert not any("test_helper" in i or "helper.py" in i for i in ids)
    assert not any("test_helper" in i for i in cmp["fixed"])
    assert any(i.endswith("test_helper") for i in cmp["new_tests_passing_ids"])
    assert not cmp.get("load_failed_main")
    v, reason, fl = dr.verdict_for(cmp, None, None, files, _agreed_differs())
    assert v == "verified" and "cross_run_settled" in fl
    assert "fail on the base and pass on the PR" in reason
    # The stored JUnit, which a re-judge reads, has the base failure and not a base pass for the helper.
    main_junit = dr.parse_junit(tmp_path / "run" / "junit-main-1.xml")
    assert any(k.endswith("test_answer") and v[0] == "failed" for k, v in main_junit.items())
    assert not any(k.endswith("test_helper") and v[0] == "passed" for k, v in main_junit.items())


def test_contree_cross_run_uses_the_plugin_retry_and_does_not_override_python_files(tmp_path, monkeypatch):
    pr = tmp_path / "side-pr"
    main = tmp_path / "side-main"
    main.mkdir()
    (pr / "tests").mkdir(parents=True)
    (pr / "tests" / "test_mod.py").write_text("def test_answer():\n    assert False\n")
    (pr / "tests" / "test_helper.py").write_text("import only_on_pr\n")
    calls = []
    helper_xml = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="1" errors="1" failures="0">
<testcase classname="" name="tests.test_helper">
<error message="collection failure">ImportError: No module named 'only_on_pr'</error>
</testcase>
</testsuite></testsuites>
"""
    answer_xml = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="1" errors="0" failures="1">
<testcase classname="tests.test_mod" name="test_answer"><failure message="AssertionError: assert 1 == 2"/></testcase>
</testsuite></testsuites>
"""

    class Sess:
        def run_op(self, side, shell, disposable, timeout, files=None):
            calls.append((side, shell, files))
            body = helper_xml if "test_helper.py" in shell else answer_xml
            out = f"___POC_EXIT___1\n___POC_JUNIT___\n{body}\n___POC_LOG___\nok\n"
            return {"stdout": out, "stderr": "", "exit_code": 1}

    from poc import contree_sandboxes

    monkeypatch.setattr(dr, "_contree_ready", lambda: True)
    monkeypatch.setattr(contree_sandboxes, "session", lambda: Sess())
    rels = ["tests/test_mod.py", "tests/test_helper.py"]
    pr_passed = {"tests.test_mod::test_answer": ("passed", ""), "tests.test_helper::test_helper": ("passed", "")}
    results = {"main": [{}], "pr": [dict(pr_passed)]}
    (tmp_path / "run").mkdir()
    files = {"all": ["pkg/mod.py", *rels, "tests/only_on_pr.py"], "package_py": ["pkg/mod.py"]}
    a = SimpleNamespace(runs=1, workers="0", test_timeout=30, run_timeout=60, pr=None, product_check=False, bench=None)
    dr.record_cross_run(
        {"files": files},
        {"main": tmp_path / "venv-main", "pr": tmp_path / "venv-pr"},
        {"main": [], "pr": rels},
        tmp_path / "run",
        a,
        results,
        cwds={"main": main, "pr": pr},
    )
    assert len(calls) == 2 and {c[0] for c in calls} == {"main"}
    uploaded = {}
    for _side, shell, sent in calls:
        assert "INTERNALERROR" in shell and "-p no:" in shell
        assert "python_files" not in shell
        uploaded.update(sent or {})
    assert set(uploaded) == {f"{dr.OWN_CHECKOUT_ROOT}/tests/test_mod.py", f"{dr.OWN_CHECKOUT_ROOT}/tests/test_helper.py"}
    assert uploaded[f"{dr.OWN_CHECKOUT_ROOT}/tests/test_mod.py"] == pr / "tests" / "test_mod.py"
    assert results["main"][0]["tests.test_mod::test_answer"][0] == "failed"
    assert "tests.test_helper::test_helper" not in results["main"][0]
    cmp = dr.compare_sides(results)
    ids = dr.cross_run_test_ids(cmp, files)
    assert ids == ["tests.test_mod::test_answer"]
    assert not any("test_helper" in i for i in cmp["fixed"])


def test_dask_and_rich_shapes_stay_not_verified():
    path = Path(__file__).with_name("test_narrow_cross_run.py")
    spec = importlib.util.spec_from_file_location("narrow_cross_run_fixtures", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("dask-12645.json", "rich-4147.json"):
        _spec, files, cmp, _pp, (v, _reason, fl) = mod._judge(name)
        assert dr.cross_run_test_ids(cmp, files)
        assert v == "needs_attention"
        assert "cross_run_settled" not in fl
