"""New tests in a nested relaxed-class layout are collected and run on the base.

The file is not named test_*.py. Pytest's own collection (python_files, python_classes and
python_functions, plus whatever plugin the checkout loads) supplies the node ids. A parametrized
method and a parametrized class are both taken from that output. A file that fails to collect is
not recorded as a pass. Nothing here contacts GitHub.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ops import daily_run as dr

INI = "[pytest]\npython_files = *\npython_classes = *\npython_functions = *\n"

BASE_CHECKS = '''
class Bucket_:
    class nested:
        def old_case(self):
            assert True
'''

PR_CHECKS = '''
import pytest

class Bucket_:
    class nested:
        def old_case(self):
            assert True

        @pytest.mark.parametrize("cli_name,attr_name", [("param-1", "param_1"), ("plain", None)])
        def reports_names(self, cli_name, attr_name):
            from pkg.mod import answer
            assert answer() == 2

    @pytest.mark.parametrize("n", [1])
    class grouped:
        def sees_n(self, n):
            from pkg.mod import answer
            assert answer() == 2
'''

BOOM = "import missing_module_xyz\n"
OLD = "def test_old():\n    assert True\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _venv(work: Path, name: str) -> Path:
    """A side interpreter that imports the pytest the test runner already has."""
    import pytest as pytest_mod

    venv = work / name
    bindir = venv / "bin"
    bindir.mkdir(parents=True)
    (bindir / "python").symlink_to(sys.executable)
    ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    sp = venv / "lib" / ver / "site-packages"
    sp.mkdir(parents=True)
    (sp / "runner.pth").write_text(str(Path(pytest_mod.__file__).resolve().parent.parent) + "\n")
    (venv / "pyvenv.cfg").write_text(
        f"home = {Path(sys.executable).resolve().parent}\ninclude-system-site-packages = false\n"
        f"version = {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\n"
    )
    return venv


def _tree(root: Path, answer: str, checks: str, ini: str = INI) -> None:
    _write(root / "pytest.ini", ini)
    _write(root / "pkg" / "__init__.py", "")
    _write(root / "pkg" / "mod.py", f"def answer():\n    return {answer}\n")
    _write(root / "tests" / "__init__.py", "")
    _write(root / "tests" / "test_old.py", OLD)
    _write(root / "tests" / "checks.py", checks)
    _write(root / "tests" / "boom.py", BOOM)


def _files() -> dict:
    return {
        "all": ["pkg/mod.py", "tests/checks.py", "tests/boom.py", "tests/test_old.py"],
        "package_py": ["pkg/mod.py"],
        "compiled": [],
        "other": ["tests/checks.py", "tests/boom.py"],
    }


def _run(tmp_path: Path, base_answer: str, pr_answer: str, ini: str = INI):
    pytest.importorskip("pytest_timeout")
    from guardrails import sandbox

    work = tmp_path / "work"
    main, pr = work / "side-main", work / "side-pr"
    _tree(main, base_answer, BASE_CHECKS, ini)
    _tree(pr, pr_answer, PR_CHECKS, ini)
    venvs = {"main": _venv(work, "venv-main"), "pr": _venv(work, "venv-pr")}
    rec = {"files": _files(), "base_ref": "main"}
    rundir = tmp_path / "run"
    rundir.mkdir()
    targets = {"main": ["tests/test_old.py"], "pr": ["tests/test_old.py"]}
    a = SimpleNamespace(runs=1, workers="0", test_timeout=60, run_timeout=120, build_timeout=60,
                        pr="https://github.com/o/r/pull/1", product_check=False, bench=None)
    was = sandbox.enabled()
    sandbox.configure(False)
    try:
        cmp, cnv, _ex = dr.execute_tests(rec, venvs, targets, rundir, work, a,
                                         cwds={"main": main, "pr": pr})
    finally:
        sandbox.configure(was)
    return rec, cmp, cnv, rundir, main, pr


def _collected(log: Path, root: Path) -> list[str]:
    return dr.collect_node_ids(log.read_text(errors="replace"), root)


def test_collect_node_ids_keep_parametrized_lines_and_drop_the_command():
    text = "\n".join([
        "$ python -m pytest tests/checks.py --collect-only -q",
        "tests/checks.py::Bucket_::nested::reports_names[param-1-param_1]",
        "tests/checks.py::Bucket_::grouped::sees_n[1]",
        "tests/checks.py::Bucket_::nested::reports_names[a value]",
        "ERROR collecting tests/boom.py",
        "2 tests collected in 0.01s",
    ])
    ids = dr.collect_node_ids(text, None)
    assert ids == [
        "tests/checks.py::Bucket_::nested::reports_names[param-1-param_1]",
        "tests/checks.py::Bucket_::grouped::sees_n[1]",
        "tests/checks.py::Bucket_::nested::reports_names[a value]",
    ]


def test_nested_relaxed_tests_are_collected_and_fail_on_the_base(tmp_path):
    """A nested class added on the PR is absent on the base file, fails there, and passes on the PR."""
    rec, cmp, cnv, rundir, main, pr = _run(tmp_path, "1", "2")
    assert cnv is None and cmp is not None
    assert "reports_names" not in (main / "tests" / "checks.py").read_text()
    pr_log = rundir / "collect-cross-pr-tests_checks.py.log"
    base_log = rundir / "collect-cross-main-tests_checks.py.log"
    assert pr_log.is_file() and base_log.is_file()
    pr_ids = _collected(pr_log, pr)
    base_ids = _collected(base_log, main)
    new = [node for node in pr_ids if node not in set(base_ids)]
    assert new, pr_log.read_text()
    # Both decorator styles are whatever pytest printed, not a name this runner invented.
    assert any("param-1" in node for node in new)
    assert any(node.endswith("[1]") for node in new)
    assert len([node for node in new if "[" in node]) >= 2
    info = cmp["base_new_tests"]
    assert info["ids"] == sorted(new)
    assert not info["passed_on_base"]
    assert set(info["failed_on_base"]) == set(new)
    assert info["reproduced"] is True
    assert not info["not_collected"]
    assert "tests/boom.py" in info["collection_failed"]
    assert "tests/checks.py" not in info["collection_failed"]
    ids = dr.cross_run_test_ids(cmp, rec["files"])
    assert ids
    assert {dr._canon_test_id(tid, pr, ["tests/checks.py"]) for tid in ids} == set(new)
    assert not any("old_case" in tid or "boom" in tid or "test_old" in tid for tid in ids)
    # The base junit, which a re-judge reads, recorded the failure. Nothing from the broken file passed.
    main_junit = dr.parse_junit(rundir / "junit-main-1.xml")
    assert any(row[0] == "failed" for row in main_junit.values())
    assert not any(tid.endswith("boom") and row[0] == "passed" for tid, row in main_junit.items())
    assert dr.already_on_base_message(cmp, "main") is None
    for node in new:
        assert node in pr_log.read_text()


def test_pytest_relaxed_finds_nested_classes_without_class_name_globs(tmp_path):
    """The plugin, not a python_classes setting, is what collects the nested tests. Same runner either way."""
    pytest.importorskip("pytest_relaxed")
    _rec, cmp, cnv, rundir, main, pr = _run(tmp_path, "1", "2", ini="[pytest]\npython_files = *\n")
    assert cnv is None and cmp is not None
    pr_log = rundir / "collect-cross-pr-tests_checks.py.log"
    base_log = rundir / "collect-cross-main-tests_checks.py.log"
    new = [node for node in _collected(pr_log, pr) if node not in set(_collected(base_log, main))]
    assert any("param-1" in node for node in new)
    assert any(node.endswith("[1]") for node in new)
    assert set(cmp["base_new_tests"]["failed_on_base"]) == set(new)
    assert cmp["base_new_tests"]["reproduced"] is True
    assert dr.cross_run_test_ids(cmp, _rec["files"])


def test_new_tests_that_pass_on_the_base_are_not_a_missing_collection(tmp_path):
    """When the new tests pass on the base, the failure was not reproduced. The verdict is not promoted."""
    rec, cmp, cnv, rundir, main, pr = _run(tmp_path, "2", "2")
    assert cnv is None and cmp is not None
    pr_log = rundir / "collect-cross-pr-tests_checks.py.log"
    base_log = rundir / "collect-cross-main-tests_checks.py.log"
    # Collected before the pull-request file was copied onto the base, so the new ids are absent there.
    new = [node for node in _collected(pr_log, pr) if node not in set(_collected(base_log, main))]
    assert new and all("[" in node for node in new)
    info = cmp["base_new_tests"]
    assert set(info["passed_on_base"]) == set(new)
    assert not info["failed_on_base"] and not info["not_collected"]
    assert info["reproduced"] is False
    assert dr.cross_run_test_ids(cmp, rec["files"]) == []
    before = dr.verdict_for(cmp, None, None, rec["files"])
    dr._store_verdict(rec, cmp, None, None)
    assert rec["verdict"] == before[0]
    assert rec["already_on_base"] == "fix appears already present on main"
    assert rec["reason"].endswith("fix appears already present on main")
    assert "tests/boom.py" in info["collection_failed"]
    assert not any("boom" in node for node in info["passed_on_base"])


def test_already_on_base_needs_every_new_test_and_does_not_change_needs_attention():
    """One passing test, or a test that was not collected, is not the note. needs_attention stays."""
    full = {"ids": ["tests/checks.py::Bucket_::nested::reports_names[param-1-param_1]",
                    "tests/checks.py::Bucket_::grouped::sees_n[1]"],
            "passed_on_base": ["tests/checks.py::Bucket_::nested::reports_names[param-1-param_1]",
                               "tests/checks.py::Bucket_::grouped::sees_n[1]"],
            "failed_on_base": [], "not_collected": [], "reproduced": False}
    assert dr.already_on_base_message({"base_new_tests": full}, "main") == "fix appears already present on main"
    assert dr.already_on_base_message({"base_new_tests": full}, "master") == "fix appears already present on master"
    assert dr.already_on_base_message({"base_new_tests": full}, "") == "fix appears already present on main"
    unrelated = {"ids": [], "passed_on_base": ["tests/test_old.py::test_old"], "failed_on_base": [],
                 "not_collected": [], "reproduced": False}
    assert dr.already_on_base_message({"base_new_tests": unrelated}, "main") is None
    missed = dict(full, passed_on_base=full["passed_on_base"][:1], not_collected=full["ids"][1:])
    assert dr.already_on_base_message({"base_new_tests": missed}, "main") is None
    reproduced = dict(full, failed_on_base=full["ids"], passed_on_base=[], reproduced=True)
    assert dr.already_on_base_message({"base_new_tests": reproduced}, "main") is None
    one = dict(full, ids=full["ids"][:1], passed_on_base=full["passed_on_base"][:1])
    # A single new test that really passed is enough; an unrelated extra pass is not what decides it.
    assert dr.already_on_base_message({"base_new_tests": one}, "main") == "fix appears already present on main"
    rec = {"verdict": "needs_attention", "reason": "1 test(s) pass on main but fail on the PR", "base_ref": "main"}
    dr._attach_already_on_base(rec, {"base_new_tests": full})
    assert rec["verdict"] == "needs_attention"
    assert rec["already_on_base"] == "fix appears already present on main"
    assert "fix appears already present on main" in rec["reason"]
    dr._attach_already_on_base(rec, {"base_new_tests": unrelated})
    assert rec["verdict"] == "needs_attention"
    assert "already_on_base" not in rec
    assert "fix appears already present" not in rec["reason"]


def test_the_note_is_in_the_report_and_the_pdf(tmp_path):
    from reports.pr_report import build
    from reports.reviewer import to_html, to_pdf

    phrase = "fix appears already present on main"
    record = {"schema_version": "1", "record_kind": "pr_run", "id": "pr-acme-widget-1",
              "repo": "acme/widget", "pr": {"repo": "acme/widget", "number": 1, "url": "https://example.test/1",
                                            "title": "t", "head_sha": "a" * 40},
              "author": "a", "route": "source-pair", "verdict": "needs_attention",
              "reason": f"1 test(s) pass on main but fail on the PR; {phrase}",
              "already_on_base": phrase, "base_ref": "main",
              "files": {"all": ["pkg/mod.py"], "package_py": ["pkg/mod.py"], "compiled": []},
              "updated_at_ist": "x", "ci_state": "none", "ci_detail": "-",
              "runs_per_side": 1, "runs_per_side_planned": 1, "per_run": [],
              "duration_s": {"total_wall": 1}, "network": "allowed", "posted_upstream": False,
              "logs": "widget-1/", "tested_at_ist": "2026-11-06 00:00 IST",
              "coverage_gate": {"kind": "measured", "changed": False, "confidence": "high", "note": "n",
                                "measurement": "measured"}}
    rundir = tmp_path / "run"
    rundir.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    report, decision = build(record, rundir, out)
    assert record["verdict"] == "needs_attention"
    blob = "\n".join(str(block) for block in report.blocks)
    assert phrase in blob
    assert decision["verdict"] != "VERIFIED"
    html = out / "report.html"
    pdf = out / "report.pdf"
    html.write_text(to_html(report, "report"))
    err = to_pdf(str(html), str(pdf))
    assert err is None and pdf.is_file() and pdf.stat().st_size > 0
    assert phrase in _pdf_strings(pdf)
    assert record["verdict"] == "needs_attention"


def _pdf_strings(path: Path) -> str:
    """Text drawn by the built-in PDF maker (ASCII85 and Flate streams, then the literal strings)."""
    import base64
    import re
    import zlib
    raw = path.read_bytes()
    parts = []
    for match in re.finditer(rb"/Length (\d+)\s*>>\s*stream\n", raw):
        window = raw[max(0, match.start() - 160):match.start()]
        data = raw[match.end():match.end() + int(match.group(1))].strip()
        try:
            if data.endswith(b"~>"):
                data = data[:-2]
            if b"ASCII85Decode" in window:
                data = base64.a85decode(data, adobe=False)
            if b"FlateDecode" in window:
                data = zlib.decompress(data)
        except (ValueError, zlib.error):
            continue
        parts.append(data.decode("latin-1", "ignore"))
    drawn = " ".join(re.findall(r"\((?:\\.|[^)\\])*\)", "\n".join(parts)))
    return drawn + "\n" + "\n".join(parts)
