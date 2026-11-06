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
    # collection_failed is not a verdict_for input. The tests that ran match, so the default is verified.
    assert before[0] == "verified"
    dr._store_verdict(rec, cmp, None, None)
    # The note applies and tests/boom.py failed to collect, so only this verified result is capped.
    assert rec["verdict"] == "could_not_verify"
    assert rec["verdict"] != "needs_attention"
    assert "could not verify:" in rec["reason"]
    assert rec["already_on_base"] == "fix appears already present on main"
    assert "fix appears already present on main" in rec["reason"]
    assert "tests/boom.py" in info["collection_failed"]
    assert "tests/boom.py" in rec["collection_limitation"]
    assert "tests/boom.py" in rec["reason"]
    # The cap names the file, then the note, then the limitation sentence beside the note.
    assert rec["reason"].index("fix appears already present on main") < rec["reason"].index(rec["collection_limitation"])
    assert "clean verification" not in rec["reason"].lower()
    assert "clean verification" not in rec["collection_limitation"].lower()
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
    # A different file that failed to collect does not block the note. The identified new tests still count.
    other = dict(full, collection_failed=["tests/other_changed.py"])
    assert dr.already_on_base_message({"base_new_tests": other}, "2.2") == "fix appears already present on 2.2"
    assert dr.already_on_base_message({"base_new_tests": other}, "master") == "fix appears already present on master"
    # The file that itself failed to collect produced no new ids, so there is no note. The failure is still named.
    blocked = {"ids": [], "passed_on_base": [], "failed_on_base": [], "not_collected": [],
               "reproduced": False, "collection_failed": ["tests/checks.py"]}
    assert dr.already_on_base_message({"base_new_tests": blocked}, "main") is None
    rec = {"verdict": "needs_attention", "reason": "1 test(s) pass on main but fail on the PR", "base_ref": "main"}
    dr._attach_already_on_base(rec, {"base_new_tests": full})
    assert rec["verdict"] == "needs_attention"
    assert rec["already_on_base"] == "fix appears already present on main"
    assert "fix appears already present on main" in rec["reason"]
    dr._attach_already_on_base(rec, {"base_new_tests": unrelated})
    assert rec["verdict"] == "needs_attention"
    assert "already_on_base" not in rec
    assert "fix appears already present" not in rec["reason"]
    held = {"verdict": "verified", "reason": "no difference on the tests that ran", "base_ref": "2.2"}
    dr._attach_already_on_base(held, {"base_new_tests": other})
    assert held["verdict"] == "verified"
    assert held["already_on_base"] == "fix appears already present on 2.2"
    assert "tests/other_changed.py" in held["collection_limitation"]
    assert held["reason"].index("fix appears already present on 2.2") < held["reason"].index("tests/other_changed.py")
    assert "clean verification" not in held["reason"].lower()
    dr._attach_already_on_base(held, {"base_new_tests": other})
    assert held["reason"].count("tests/other_changed.py") == 1
    assert held["reason"].count("fix appears already present on 2.2") == 1
    assert held["verdict"] == "verified"
    missed_only = {"verdict": "verified", "reason": "no difference on the tests that ran", "base_ref": "master"}
    dr._attach_already_on_base(missed_only, {"base_new_tests": blocked})
    assert missed_only["verdict"] == "verified"
    assert "already_on_base" not in missed_only
    assert "tests/checks.py" in missed_only["collection_limitation"]
    assert missed_only["verdict"] == "verified"
    both = dict(full, collection_failed=["tests/other_changed.py", "tests/also_changed.py"])
    named = dr.collection_limitation_message({"base_new_tests": both})
    assert "tests/other_changed.py" in named and "tests/also_changed.py" in named
    assert "clean verification" not in named.lower()


def test_default_verdict_inputs_and_the_verified_only_cap():
    """verdict_for does not read collection_failed. Only a verified result with the note is capped.

    A comparison that needs attention stays needs attention. The note is not removed.
    """
    passed = {"tests/test_old.py::test_old": ("passed", "")}
    files = {"all": ["pkg/mod.py", "tests/other_changed.py"], "package_py": ["pkg/mod.py"], "compiled": []}
    clean = dr.compare_sides({"main": [passed], "pr": [passed]})
    default = dr.verdict_for(clean, None, None, files)
    assert default[0] == "verified"
    gap = {"ids": ["tests/checks.py::Bucket_::nested::reports_names[param-1]"],
           "passed_on_base": ["tests/checks.py::Bucket_::nested::reports_names[param-1]"],
           "failed_on_base": [], "not_collected": [], "reproduced": False,
           "collection_failed": ["tests/other_changed.py"]}
    clean["base_new_tests"] = gap
    still = dr.verdict_for(clean, None, None, files)
    assert still[0] == "verified"
    capped_v, capped_reason = dr.cap_for_uncollected_file(clean, still[0], still[1])
    assert capped_v == "could_not_verify"
    assert "tests/other_changed.py" in capped_reason
    assert "clean verification" not in capped_reason.lower()
    rec = {"verdict": capped_v, "reason": capped_reason, "base_ref": "2.2"}
    dr._attach_already_on_base(rec, clean)
    assert rec["verdict"] == "could_not_verify"
    assert rec["already_on_base"] == "fix appears already present on 2.2"
    assert "tests/other_changed.py" in rec["reason"]
    failed = {"tests/test_old.py::test_old": ("failed", "AssertionError: no")}
    attention = dr.compare_sides({"main": [passed], "pr": [failed]})
    attention["base_new_tests"] = gap
    found = dr.verdict_for(attention, None, None, files)
    assert found[0] == "needs_attention"
    held_v, held_reason = dr.cap_for_uncollected_file(attention, found[0], found[1])
    assert (held_v, held_reason) == found[:2]
    kept = {"verdict": held_v, "reason": held_reason, "base_ref": "master"}
    dr._attach_already_on_base(kept, attention)
    assert kept["verdict"] == "needs_attention"
    assert kept["already_on_base"] == "fix appears already present on master"
    assert "tests/other_changed.py" in kept["collection_limitation"]
    # No note: a collection failure alone does not cap a verified result.
    plain = dr.compare_sides({"main": [passed], "pr": [passed]})
    plain["base_new_tests"] = {"ids": [], "passed_on_base": [], "failed_on_base": [], "not_collected": [],
                               "reproduced": False, "collection_failed": ["tests/checks.py"]}
    again = dr.verdict_for(plain, None, None, files)
    assert again[0] == "verified"
    assert dr.cap_for_uncollected_file(plain, again[0], again[1])[0] == "verified"


def _report_record(verdict: str, base_ref: str, failed: str) -> dict:
    """A record whose own checks pass, so the report shows the stored verdict."""
    phrase_ref = base_ref or "main"
    reason = ("no difference on the tests that ran" if verdict == "verified"
              else "1 test(s) pass on main but fail on the PR")
    rec = {"schema_version": "1", "record_kind": "pr_run", "id": "pr-acme-widget-1",
           "repo": "acme/widget", "pr": {"repo": "acme/widget", "number": 1, "url": "https://example.test/1",
                                         "title": "t", "head_sha": "a" * 40},
           "author": "a", "route": "source-pair", "verdict": verdict, "reason": reason,
           "base_ref": base_ref, "title": "t",
           "files": {"all": ["pkg/mod.py", failed], "package_py": ["pkg/mod.py"], "compiled": []},
           "updated_at_ist": "x", "ci_state": "none", "ci_detail": "-",
           "runs_per_side": 3, "runs_per_side_planned": 3,
           "per_run": [{"side": side, "exit": 0} for side in ("old", "new") for _ in range(3)],
           "duration_s": {"total_wall": 1}, "network": "allowed", "posted_upstream": False,
           "logs": "widget-1/", "tested_at_ist": "2026-11-06 00:00 IST",
           "thread_env": {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                          "NUMEXPR_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1", "BLIS_NUM_THREADS": "1",
                          "PYTHONHASHSEED": "0"},
           "machine_type": {"label": "local", "arch": "x86_64", "cpu_count": 2},
           "coverage_gate": {"kind": "measured", "changed": False, "confidence": "high", "note": "measured",
                             "measurement": "measured"},
           "comparison": {"base_new_tests": {
               "ids": ["tests/checks.py::Bucket_::nested::reports_names[param-1]"],
               "passed_on_base": ["tests/checks.py::Bucket_::nested::reports_names[param-1]"],
               "failed_on_base": [], "not_collected": [], "reproduced": False,
               "collection_failed": [failed]}}}
    dr._attach_already_on_base(rec, rec["comparison"])
    assert rec["already_on_base"] == f"fix appears already present on {phrase_ref}"
    assert rec["verdict"] == verdict
    return rec


def test_collection_failure_stays_beside_the_note_and_is_not_hidden(tmp_path, monkeypatch):
    """A different changed file that fails to collect is named beside the note.

    needs_attention stays needs attention. A record stored as could_not_verify, because a verified
    comparison was capped, shows that verdict and still shows the note and the file.
    """
    from poc import pdf_always
    from reports.pr_report import build
    from reports.reviewer import to_html, to_pdf, write_summary

    monkeypatch.setattr("reports.reviewer.latest_replay", lambda: None)
    failed = "tests/other_changed.py"
    cases = (("could_not_verify", "2.2", "COULD NOT VERIFY", "Re-run"),
             ("needs_attention", "master", "NEEDS ATTENTION", "Reject"))
    for verdict, base_ref, shown, action in cases:
        record = _report_record(verdict, base_ref, failed)
        phrase = record["already_on_base"]
        rundir = tmp_path / f"run-{verdict}"
        rundir.mkdir()
        out = tmp_path / f"out-{verdict}"
        out.mkdir()
        report, row = build(record, rundir, out)
        assert record["verdict"] == verdict
        assert row["verdict"] == shown
        assert row["action"] == action
        if verdict == "needs_attention":
            assert row["verdict"] != "COULD NOT VERIFY"
        blob = "\n".join(str(block) for block in report.blocks)
        assert phrase in blob
        assert failed in blob
        assert "clean verification" not in blob.lower()
        assert "Nothing to fix" not in blob
        assert "The PR's tests behave the same or better than on main" not in blob
        paras = [block[1] for block in report.blocks if block[0] == "p"]
        note_at = next(i for i, text in enumerate(paras) if text.strip() == phrase)
        assert failed in paras[note_at + 1]
        html = out / "report.html"
        pdf = out / "report.pdf"
        html.write_text(to_html(report, "report"))
        err = to_pdf(str(html), str(pdf))
        assert err is None and pdf.is_file() and pdf.stat().st_size > 0
        drawn = _pdf_strings(pdf)
        assert phrase in drawn
        assert failed in drawn
        assert "clean verification" not in drawn.lower()
        assert "hidden" not in drawn.lower()
        record["_pr_id"] = f"widget-{verdict}"
        summary = dr.combined_run_summary_md([record], "go")
        assert "Nothing needs attention" not in summary
        assert failed in summary
        assert "already present on" in summary
        assert "clean verification" not in summary.lower()
        assert f"**{shown}**" in summary or "**VERIFIED**" in summary or "**NEEDS ATTENTION**" in summary
        if verdict == "could_not_verify":
            assert "**COULD NOT VERIFY**" in summary
            assert "**NEEDS ATTENTION**" not in summary
        else:
            assert "**NEEDS ATTENTION**" in summary
            assert "**COULD NOT VERIFY**" not in summary
            assert record["verdict"] == "needs_attention"

    capped = _report_record("could_not_verify", "2.2", failed)
    daily = tmp_path / "daily"
    daily.mkdir()
    (tmp_path / "run-daily").mkdir()
    _report, row = build(capped, tmp_path / "run-daily", daily)
    write_summary([row], str(daily), "go", ("md",))
    daily_md = (daily / "SUMMARY.md").read_text()
    assert "Nothing needs attention" not in daily_md
    assert failed in daily_md
    assert "clean verification" not in daily_md.lower()
    assert "COULD NOT VERIFY" in daily_md
    fallback = tmp_path / "fallback"
    pdf_always.records_pdfs(fallback, "run", [("widget-1", capped)])
    summary_pdf = _pdf_strings(fallback / "SUMMARY.pdf")
    per_pdf = _pdf_strings(fallback / "widget-1" / "REPORT.pdf")
    assert failed in summary_pdf and failed in per_pdf
    assert "NO-GO, could not verify" in summary_pdf
    assert "Go/no-go: GO" not in summary_pdf
    assert "clean verification" not in summary_pdf.lower()
    assert "clean verification" not in per_pdf.lower()
    assert "could not verify" in per_pdf.lower()
    assert capped["verdict"] == "could_not_verify"


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
