"""The coverage gate never counts a bad or partial coverage report as measured."""
import json
from types import SimpleNamespace

import pytest

from poc import coverage_gate
from tests.test_contree_only import _gate, _sides, daily_run


def test_missing_changed_file_is_not_measured():
    cov = coverage_gate.measure({"pkg/a.py": {1, 2}, "pkg/b.py": {3}},
                                {"/x/pkg/a.py": {"executed_lines": [1, 2], "missing_lines": []}})
    assert cov["status"] == "not measured" and "pkg/b.py" in cov["why"]


def test_report_without_the_only_changed_file_cannot_verify():
    cov = coverage_gate.measure({"widget/core.py": {2}}, {"/work/src/other.py": {"executed_lines": [1],
                                                                                  "missing_lines": []}})
    assert cov["status"] == "not measured"
    assert _gate(cov)["verdict"] == "could_not_verify"


@pytest.mark.parametrize("files", [{}, None, [], "x"])
def test_empty_or_wrong_files_is_not_measured(files):
    assert coverage_gate.measure({"pkg/a.py": {1}}, files)["status"] == "not measured"


@pytest.mark.parametrize("entry", [{"executed_lines": "1,2"}, {"executed_lines": [1], "missing_lines": None},
                                   {"executed_lines": ["1"]}, [1, 2], None])
def test_badly_shaped_entry_is_not_measured(entry):
    cov = coverage_gate.measure({"pkg/a.py": {1}}, {"pkg/a.py": entry})
    assert cov["status"] == "not measured" and "badly shaped" in cov["why"]


@pytest.mark.parametrize("text,why", [("not json", "not valid JSON"), ("[1]", "badly shaped"),
                                      ('{"files": []}', "badly shaped"), ('{"files": {}}', "no files"),
                                      ('{"meta": {}}', "badly shaped"), ("", "no data")])
def test_parse_report_rejects_malformed(text, why):
    files, reason = coverage_gate.parse_report(text)
    assert files is None and why in reason


def test_only_changed_lines_count_as_covered():
    cov = coverage_gate.measure({"pkg/a.py": {5}},
                                {"pkg/a.py": {"executed_lines": [1, 2, 3, 4, 6, 7], "missing_lines": [5]}})
    assert cov["status"] == "measured"
    assert cov["changed_lines_total"] == 1 and cov["changed_lines_covered"] == 0
    rec = {"verdict": "verified", "reason": "ok", "product_check": True, "files": {"all": ["pkg/a.py"]},
           "coverage": cov}
    assert coverage_gate.apply(rec)["verdict"] == "could_not_verify"


def _run(tmp_path, monkeypatch, run_op):
    main_root, pr_root, item, a = _sides(tmp_path)
    monkeypatch.setattr("poc.contree_sandboxes.session", lambda: SimpleNamespace(pr_uuid="pr-1", run_op=run_op))
    return daily_run.contree_coverage_run(item, main_root, pr_root, ["tests/test_widget.py"], tmp_path, a)


@pytest.mark.parametrize("exc", [TimeoutError("slow"), RuntimeError("contree down")])
def test_contree_error_or_timeout_is_not_measured(tmp_path, monkeypatch, exc):
    def boom(*a, **k):
        raise exc
    got = _run(tmp_path, monkeypatch, boom)
    assert got["status"] == "not measured" and "Contree coverage run failed" in got["why"]
    assert _gate(got)["verdict"] == "could_not_verify"


@pytest.mark.parametrize("body", ["{oops", json.dumps({"files": {}}),
                                  json.dumps({"files": {"/work/src/other.py": {"executed_lines": [1],
                                                                               "missing_lines": []}}})])
def test_contree_bad_or_partial_report_caps(tmp_path, monkeypatch, body):
    def op(*a, **k):
        return {"exit_code": 0, "stdout": f"___POC_EXIT___0\n___POC_COV_START___\n{body}\n___POC_COV_END___\n"}
    got = _run(tmp_path, monkeypatch, op)
    assert got["status"] == "not measured"
    assert _gate(got)["verdict"] == "could_not_verify"


def _partial(product: bool, a_exec):
    cov = coverage_gate.measure({"pkg/a.py": {1, 2}, "pkg/b.py": {3}},
                                {"/x/pkg/a.py": {"executed_lines": a_exec,
                                                 "missing_lines": [n for n in (1, 2) if n not in a_exec]}})
    assert cov["status"] == "not measured" and "pkg/b.py" in cov["why"]
    rec = {"verdict": "verified", "reason": "1 new test(s) pass", "files": {"all": ["pkg/a.py", "pkg/b.py"]},
           "coverage": cov}
    if product:
        rec["product_check"] = True
    return coverage_gate.apply(rec)


@pytest.mark.parametrize("product", [False, True])
def test_partial_report_with_listed_file_never_run_caps_never_ran(product):
    out = _partial(product, [])
    assert out["verdict"] == "could_not_verify"
    assert "never ran" in out["reason"] and "pkg/a.py" in out["reason"]


def test_partial_report_all_listed_ran_stays_not_measured_non_product():
    out = _partial(False, [1, 2])
    assert out["verdict"] == "verified" and out["coverage_gate"]["measurement"] == "not measured"
    assert out["coverage_gate"]["confidence"] == "lower"


def test_partial_report_all_listed_ran_product_stays_capped():
    out = _partial(True, [1, 2])
    assert out["verdict"] == "could_not_verify" and out["reason"].startswith(coverage_gate.PRODUCT_NOT_MEASURED)
    assert "never ran" not in out["reason"]
