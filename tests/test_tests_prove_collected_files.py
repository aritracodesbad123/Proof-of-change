"""The tests-prove rule accepts a test file the run collected, not only test_*.py.

The cross-run settlement set stays on default-named edited test files. A shared id is still not proof.
"""
from ops.daily_run import (
    compare_sides,
    cross_run_test_ids,
    ids_that_prove_the_change,
    verdict_for,
)
from ops.daily_run import (
    tests_prove_the_change as prove_the_change,
)
from poc import probes

FILES = {"all": ["pkg/program.py", "tests/program.py"]}
COVERAGE = {"status": "measured", "changed_lines_total": 3, "changed_lines_covered": 3}
NODE = "tests.program.Program::test_help"
DIFFERS = [{"id": "C3", "text": "help now prints", "covers": ["c3.*"], "expect": "differs"}]


def _comparison(node=NODE, shared=False):
    main = {node: ("failed", "AssertionError"), "tests/program.py::test_keep": ("passed", "")}
    pr = {node: ("passed", ""), "tests/program.py::test_keep": ("passed", "")}
    cmp = compare_sides({"main": [main] * 3, "pr": [pr] * 3})
    cmp["collected_test_files"] = ["tests/program.py"]
    if shared:
        cmp["base_new_tests"] = {"shared_ids": [node]}
    return cmp


def _probe(main, pr):
    spec = {"id": "model-p1", "target": "o/r#1", "about": "x", "claims": DIFFERS, "source": "model"}
    item = probes.entry(spec, {"main": [main] * 3, "pr": [pr] * 3}, {"main": ["m"], "pr": ["p"]}, [], "model", None)
    item["probe_changed_line_coverage"] = {"status": "measured", "changed_lines_covered": 1,
                                           "changed_lines_total": 1, "adequacy": "adequate"}
    return {"status": "ran", "items": [item]}


def test_a_collected_file_that_is_not_named_test_py_proves_the_change():
    cmp = _comparison()
    assert cross_run_test_ids(cmp, FILES) == []
    assert ids_that_prove_the_change(cmp, FILES) == [NODE]
    assert prove_the_change(cmp, FILES, COVERAGE)
    pp = _probe({"c3.shown.result": "old", "c3.control.result": "held"},
                {"c3.shown.result": "new", "c3.control.result": "held"})
    v, reason, fl = verdict_for(cmp, None, None, FILES, pp, coverage=COVERAGE)
    by_name = {o["name"]: o for o in pp["items"][0]["observations"]}
    assert by_name["c3.control.result"]["linked_by"] == "tests_prove"
    assert by_name["c3.shown.result"]["label"] == "proven"
    assert v == "verified"
    assert "tests_prove_not_verified" not in fl
    assert "may not reach the changed code" in reason


def test_a_junit_path_counts_without_the_collected_list():
    cmp = _comparison()
    cmp.pop("collected_test_files")
    # The junit id already names the file, which is what collection recorded.
    cmp["fixed"] = ["tests/program.py::Program::test_help"]
    assert ids_that_prove_the_change(cmp, FILES) == ["tests/program.py::Program::test_help"]
    assert prove_the_change(cmp, FILES, COVERAGE)


def test_a_collected_file_the_pull_request_did_not_edit_does_not_prove_the_change():
    cmp = _comparison()
    cmp["collected_test_files"] = ["tests/program.py", "tests/untouched.py"]
    cmp["fixed"] = ["tests/untouched.py::test_flake"]
    assert "tests/untouched.py::test_flake" not in ids_that_prove_the_change(cmp, FILES)
    assert ids_that_prove_the_change(cmp, FILES) == []
    assert not prove_the_change(cmp, FILES, COVERAGE)
    # The edited collected file still counts when its own fail-then-pass is present.
    both = _comparison()
    both["collected_test_files"] = ["tests/program.py", "tests/untouched.py"]
    both["fixed"] = list(both["fixed"]) + ["tests/untouched.py::test_flake"]
    got = ids_that_prove_the_change(both, FILES)
    assert NODE in got
    assert "tests/untouched.py::test_flake" not in got


def test_a_file_the_run_did_not_collect_does_not_prove_the_change():
    cmp = _comparison()
    cmp.pop("collected_test_files")
    # This id does not resolve to a changed file, so it was not a collected test of this change.
    cmp["fixed"] = ["other.module.Test::test_help"]
    assert ids_that_prove_the_change(cmp, FILES) == []
    assert not prove_the_change(cmp, FILES, COVERAGE)


def test_a_shared_id_in_a_collected_file_is_not_proof():
    cmp = _comparison(shared=True)
    assert NODE not in ids_that_prove_the_change(cmp, FILES)
    assert not prove_the_change(cmp, FILES, COVERAGE)


def test_an_agreeing_probe_alone_still_does_not_verify_from_a_collected_file():
    cmp = _comparison()
    pp = _probe({"c3.control.result": "old"}, {"c3.control.result": "old"})
    v, _reason, fl = verdict_for(cmp, None, None, FILES, pp, coverage=COVERAGE)
    # The cross-run does not settle this file, and the agreeing note is not proof by itself.
    # Every observation agrees, so the cross-run's own settlement set is empty and the note must not verify.
    assert pp["items"][0]["observations"][0]["linked_by"] == "tests_prove"
    assert v == "could_not_verify"
    assert "tests_prove_not_verified" in fl
