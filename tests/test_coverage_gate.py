"""Coverage gate (poc/coverage_gate.py): 'verified' must mean the PR's changed code was exercised."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from poc import coverage_gate as cg

ROOT = Path(__file__).parent.parent
DAY1 = ROOT / "tests" / "fixtures" / "day1"


def _day1(name):
    return json.loads((DAY1 / name).read_text())


def _py_rec(total, covered, verdict="verified", reason="0 new test(s) pass, 50 unchanged"):
    return {"verdict": verdict, "reason": reason,
            "files": {"all": ["widget/core.py", "widget/tests/test_core.py", "docs/index.rst"],
                      "package_py": ["widget/core.py", "widget/tests/test_core.py"], "compiled": [], "other": []},
            "coverage": {"status": "measured", "changed_lines_total": total, "changed_lines_covered": covered,
                         "files": [{"file": "widget/core.py", "changed_lines_total": total,
                                    "changed_lines_covered": covered}]}}


def test_numpy_32910_is_not_fully_verified():
    """Day 1: numpy#32910 changes only item_selection.c (+ a benchmark) and adds no test. Its tests passed, so the
    run said 'verified'; the C change was never exercised by anything the PR added, so it is not fully verified."""
    rec = _day1("pr_run_numpy_32910.json")
    assert rec["verdict"] == "verified" and rec["route"] == "source-build"
    g = cg.apply(rec)
    assert g["verdict"] == "could_not_verify"
    assert g["reason"].startswith("not fully verified: compiled code changed (numpy/_core/src/multiarray/item_selection.c)")
    assert g["verdict_before_coverage_gate"] == "verified"
    assert g["coverage_gate"] == {"kind": "compiled", "changed": True, "confidence": "none", "note": g["coverage_gate"]["note"],
                                  "measurement": "not needed"}
    assert g["changed_lines_total"] is None and g["changed_lines_covered"] is None  # not measurable for C
    assert cg.apply(g) == g  # idempotent: a report rebuilt from a gated record gives the same answer


def test_compiled_change_with_a_test_for_it_stays_verified():
    rec = _day1("pr_run_numpy_32910.json")
    rec["files"]["all"].append("numpy/_core/tests/test_item_selection.py")
    g = cg.apply(rec)
    assert g["verdict"] == "verified" and not g["coverage_gate"]["changed"]
    assert cg.tests_for_compiled(rec["files"]) == {
        "numpy/_core/src/multiarray/item_selection.c": ["numpy/_core/tests/test_item_selection.py"]}


def test_build_config_and_benchmarks_are_not_compiled_sources():
    files = {"all": ["meson.build", "pyproject.toml", "benchmarks/benchmarks/bench_x.py", "numpy/_core/src/a.c",
                     "numpy/_core/tests/data/x.c"]}
    assert cg.compiled_sources(files) == ["numpy/_core/src/a.c"]
    assert cg.python_sources(files) == []


def test_python_changed_code_never_ran():
    g = cg.apply(_py_rec(12, 0))
    assert g["verdict"] == "could_not_verify"
    assert g["reason"].startswith("not fully verified: changed code never ran: 0 of 12 changed executable line(s) ran (0%)")
    assert (g["changed_lines_total"], g["changed_lines_covered"]) == (12, 0)


def test_python_low_coverage_keeps_verdict_but_lowers_confidence():
    g = cg.apply(_py_rec(10, 3))
    assert g["verdict"] == "verified" and g["coverage_gate"]["confidence"] == "lower"
    assert "3 of 10 changed executable line(s) ran (30%)" in g["coverage_gate"]["note"]


def test_python_well_covered_is_verified_with_normal_confidence():
    g = cg.apply(_py_rec(10, 8))
    assert g["verdict"] == "verified" and g["coverage_gate"]["confidence"] == "normal"
    assert (g["changed_lines_total"], g["changed_lines_covered"]) == (10, 8)


def test_findings_are_never_overridden():
    g = cg.apply(_py_rec(12, 0, verdict="needs_attention", reason="1 test(s) pass on main but fail on the PR"))
    assert g["verdict"] == "needs_attention" and not g["coverage_gate"]["changed"]


def test_docs_only_stays_verified_with_a_note():
    rec = {"verdict": "verified", "reason": "0 new test(s) pass, 5 unchanged",
           "files": {"all": ["doc/source/whatsnew/v3.0.rst", "README.md", "pandas/tests/test_x.py"]}}
    g = cg.apply(rec)
    assert g["verdict"] == "verified" and g["coverage_gate"]["kind"] == "no-executable-change"
    assert "no executable code changed" in g["coverage_gate"]["note"]


def test_python_not_measured_on_old_records():
    g = cg.apply(_day1("pr_run_pandas_70520.json"))
    assert g["verdict"] == "verified" and g["coverage_gate"]["confidence"] == "lower"
    assert "NOT MEASURED (record predates the coverage gate" in g["coverage_gate"]["note"]
    assert g["coverage_gate"]["measurement"] == "not measured: predates gate"


def test_record_without_file_list_is_left_alone():
    g = cg.apply({"verdict": "verified", "reason": "x"})
    assert g["verdict"] == "verified" and g["coverage_gate"]["kind"] == "unknown"


def test_changed_lines():
    assert cg.changed_lines("a\nb\nc\n", "a\nB\nc\nd\n") == {2, 4}
    assert cg.changed_lines(None, "x\ny\n") == {1, 2}
    assert cg.changed_lines("a\nb\n", "b\n") == set()  # pure deletion: nothing on the PR side to run


def test_measure_with_real_coverage_json(tmp_path):
    """End to end with coverage.py itself: only executable changed lines count; the branch that ran counts."""
    pytest.importorskip("coverage")
    pkg = tmp_path / "widget"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    old = "def f(x):\n    return x\n\n\ndef g(x):\n    return -x\n"
    new = ("def f(x):\n    # doubled now\n    if x > 0:\n        return 2 * x\n    return x\n\n\n"
           "def g(x):\n    return -x - 1\n")
    (pkg / "core.py").write_text(new)
    (tmp_path / "run.py").write_text("from widget.core import f\nassert f(3) == 6\n")
    subprocess.run([sys.executable, "-m", "coverage", "run", "--source=widget", "run.py"], cwd=tmp_path, check=True)
    subprocess.run([sys.executable, "-m", "coverage", "json", "-o", "cov.json"], cwd=tmp_path, check=True,
                   capture_output=True)
    files = json.loads((tmp_path / "cov.json").read_text())["files"]
    res = cg.measure({"widget/core.py": cg.changed_lines(old, new)}, files)
    # changed lines (difflib keeps the old `return x` as new line 5): 2 (a comment, not executable), 3, 4, 9;
    # executable: 3, 4, 9; ran: 3, 4 (g was never called)
    assert cg.changed_lines(old, new) == {2, 3, 4, 9}
    assert (res["changed_lines_total"], res["changed_lines_covered"]) == (3, 2)
    g = cg.apply({"verdict": "verified", "reason": "ok", "coverage": res,
                  "files": {"all": ["widget/core.py"]}})
    assert g["verdict"] == "verified" and "2 of 3 changed executable line(s) ran (67%)" in g["coverage_gate"]["note"]
    assert g["coverage_gate"]["confidence"] == "normal"


def test_unmeasured_file_is_reported():
    res = cg.measure({"widget/core.py": {1, 2}}, {"other.py": {"executed_lines": [1], "missing_lines": []}})
    assert res["status"] == "not measured" and "widget/core.py" in res["why"]
    assert res["files"][0]["note"] == "file not measured by coverage"


def test_report_shows_gate_and_summary_lists_changed_verdicts(tmp_path, monkeypatch):
    """pr_run records (schema rev 3+) through the reviewer generator: numpy#32910 becomes COULD NOT VERIFY /
    Review by hand; pandas#70520 stays VERIFIED with lowered confidence (coverage not measured, old record)."""
    from reports import pr_report
    run = tmp_path / "runs" / "2026-10-10"
    for name in ("pr_run_numpy_32910.json", "pr_run_pandas_70520.json"):
        rec = _day1(name)
        d = run / rec["logs"].strip("/")
        d.mkdir(parents=True)
        (d / "record.json").write_text(json.dumps(rec))
        for i in (1, 2, 3):
            for s in ("main", "pr"):
                (d / f"pytest-{s}-{i}.log").write_text("....\n10 passed in 1.00s\n")
    rows = {r["id"]: r for r in pr_report.render_run(run, tmp_path / "out", formats=("md", "html"))}
    np_ = rows["numpy-32910"]
    assert (np_["verdict"], np_["action"], np_["confidence"]) == ("COULD NOT VERIFY", "Review by hand", "Low")
    assert np_["why"].startswith("not fully verified: compiled code changed")
    pd_ = rows["pandas-70520"]
    assert (pd_["verdict"], pd_["action"], pd_["confidence"]) == ("VERIFIED", "Approve with notes", "Medium")
    rep = (tmp_path / "out" / "numpy-32910" / "REPORT.md").read_text()
    assert "Was the changed code exercised?" in rep and "changed the verdict from verified to could_not_verify" in rep
    assert "NOT FULLY VERIFIED" in rep
    prep = (tmp_path / "out" / "pandas-70520" / "REPORT.md").read_text()
    assert "`tests.groupby.test_missing::test_min_count (4 -> 4 ids)`" in prep
    summ = (tmp_path / "out" / "SUMMARY.md").read_text()
    assert "Changed by the coverage gate" in summ and "numpy/numpy#32910" in summ
    # the saved record on disk is never rewritten
    assert json.loads((run / "numpy-32910" / "record.json").read_text())["verdict"] == "verified"


def test_gated_record_validates_against_schema():
    from guardrails.schema import validate_record
    g = cg.apply(_day1("pr_run_numpy_32910.json"))
    assert validate_record(g) == []
    bad = copy.deepcopy(g)
    bad["coverage_gate"]["kind"] = "rust"
    assert validate_record(bad)


def test_single_pr_check_record_has_a_plain_run_date():
    """make check writes into <date>-check-<HHMM>/; the record's run_date must still be a date (schema pattern)."""
    from types import SimpleNamespace

    from guardrails.schema import validate_record
    from ops.daily_run import new_record
    old = _day1("numpy-32910-attempt4-record.json")
    item = {k: old[k] for k in ("pr", "title", "url", "author", "head_sha", "base_sha", "base_ref", "updated_at_utc",
                                "updated_at_ist", "ci_state", "ci_detail", "files")}
    a = SimpleNamespace(runs=3, workers="4", test_timeout=120, run_timeout=900, build_timeout=1800, python="3.12",
                        python_full="3.12.15")
    rec = new_record("numpy/numpy", {"dist": "numpy", "pkg": "numpy", "nightly": True}, item, a,
                     {"arch": "x86_64", "os": "Linux"}, "2026-10-10-check-0658")
    assert rec["run_date"] == "2026-10-10" and rec["id"].endswith("2026-10-10-check-0658")
    assert not [e for e in validate_record(rec) if "run_date" in e]
