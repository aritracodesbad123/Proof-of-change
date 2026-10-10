"""reports/pr_report.py and the ops/daily_run.py single-PR mode, on synthetic run folders (no network, no box paths)."""
import importlib.util
import json
from pathlib import Path

import pytest

from reports import pr_report

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("daily_run_mod", ROOT / "ops" / "daily_run.py")
dr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dr)

MACHINE = {"label": "test", "arch": "x86_64", "cpu_count": 4}
THREADS = {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}


def _rec(pr, verdict, reason, cmp=None, per_run=True, **kw):
    r = {"pr": pr, "repo": "acme/widget", "library": "widget", "title": f"Change {pr}", "url": f"https://github.com/acme/widget/pull/{pr}",
         "head_sha": "a" * 40, "route": "source-pair", "tested_at_ist": "2026-01-01 11:15 IST", "verdict": verdict, "reason": reason,
         "comparison": cmp, "machine_type": MACHINE, "thread_env": THREADS, "runs_per_side": 3, "posted_upstream": False,
         "files": {"package_py": [], "compiled": [], "other": []}}
    if per_run:
        r["per_run"] = [{"side": s, "run": i, "exit": 0} for i in (1, 2, 3) for s in ("main", "pr")]
    r.update(kw)
    return r


def _write(run, name, rec, pr_log="", main_log=""):
    d = run / name
    d.mkdir(parents=True)
    (d / "record.json").write_text(json.dumps(rec))
    for i in (1, 2, 3):
        (d / f"pytest-pr-{i}.log").write_text(pr_log)
        (d / f"pytest-main-{i}.log").write_text(main_log)
    return d


@pytest.fixture
def run(tmp_path):
    run = tmp_path / "ops" / "runs" / "2026-01-01"
    ok = "....\n10 passed in 1.00s\n"
    _write(run, "widget-1", _rec(1, "verified", "0 new test(s) pass, 10 unchanged", {"same": 10, "new_tests_passing": 0}), ok, ok)
    bad = "..F.\nFAILED t/test_a.py::test_round - AssertionError: 2 != 3\n1 failed, 9 passed in 1.00s\n"
    _write(run, "widget-2", _rec(2, "needs_attention", "1 test(s) pass on main but fail on the PR",
                                 {"same": 9, "new_tests_passing": 0, "regressions": ["t.test_a::test_round"],
                                  "messages": {"t.test_a::test_round": "AssertionError: 2 != 3"}}), bad, ok)
    _write(run, "widget-3", _rec(3, "could_not_verify", "source build of PR head failed", per_run=False))
    return run


def test_verdicts_and_summary_order(run, tmp_path):
    rows = {r["id"]: r for r in pr_report.render_run(run, tmp_path / "out", formats=("md", "html"))}
    assert (rows["widget-1"]["verdict"], rows["widget-1"]["action"], rows["widget-1"]["confidence"]) == ("VERIFIED", "Approve", "High")
    assert (rows["widget-2"]["verdict"], rows["widget-2"]["action"]) == ("NEEDS ATTENTION", "Reject")
    r3 = rows["widget-3"]
    assert (r3["verdict"], r3["action"], r3["confidence"]) == ("COULD NOT VERIFY", "Re-run", "Low")
    assert rows["widget-2"]["claims"][:2] == ["not testable", "false"] and rows["widget-2"]["citations"] == "PASS"
    summ = (tmp_path / "out" / "SUMMARY.md").read_text()
    assert summ.index("acme/widget#2") < summ.index("acme/widget#3") < summ.index("acme/widget#1")  # needs attention first
    assert (tmp_path / "out" / "widget-2" / "REPORT.html").exists()


def test_report_sections_and_citation(run, tmp_path):
    pr_report.render_run(run, tmp_path / "out", formats=("md",))
    md = (tmp_path / "out" / "widget-2" / "REPORT.md").read_text()
    heads = ["Summary in plain English", "Claims vs reality", "What changed in behavior", "What went right",
             "What went wrong and how to fix it", "Evals and guardrails (Nathan)", "Checklist", "Rerun command", "Evidence links"]
    assert [md.index("## " + h) for h in heads] == sorted(md.index("## " + h) for h in heads)
    assert "pytest-pr-1.log:2" in md and "«FAILED t/test_a.py::test_round" in md   # the claim cites the FAILED line
    assert "make check PR=https://github.com/acme/widget/pull/2" in md
    assert "/workspace" not in md


def test_tampered_log_means_could_not_verify(run, tmp_path):
    rows = {r["id"]: r for r in pr_report.render_run(run, tmp_path / "a", formats=("md",))}
    assert rows["widget-2"]["citations"] == "PASS"
    rec, d = pr_report.Logs(run / "widget-2"), run / "widget-2"
    r = json.loads((d / "record.json").read_text())
    rows_cl = pr_report.claims(r, rec)
    (d / "pytest-pr-1.log").write_text("rewritten\n" * 5)
    assert pr_report.verify([x["citation"] for x in rows_cl], d)[0] == "FAIL"


def test_missing_guardrail_fields_mean_could_not_verify(tmp_path):
    run = tmp_path / "r"
    _write(run, "widget-9", _rec(9, "verified", "ok", {"same": 1}, thread_env={}), "1 passed in 0.1s\n", "1 passed in 0.1s\n")
    (row,) = pr_report.render_run(run, tmp_path / "o", formats=("md",))
    assert (row["verdict"], row["action"]) == ("COULD NOT VERIFY", "Re-run")


def test_record_decision(run, tmp_path):
    out = tmp_path / "out"
    pr_report.render_run(run, out, formats=("md",))
    pr_report.record_decision(out / "widget-2", "reject", "Aritra", "breaks rounding")
    md = (out / "widget-2" / "REPORT.md").read_text()
    assert "**Decision recorded:** Reject by Aritra" in md and "breaks rounding" in md
    with pytest.raises(SystemExit):
        pr_report.record_decision(out / "widget-2", "maybe", "Aritra")


def test_parse_pr_urls():
    assert dr.parse_pr_urls(["https://github.com/pandas-dev/pandas/pull/12345",
                             "https://github.com/pandas-dev/pandas/pull/7/files"]) == {"pandas-dev/pandas": [12345, 7]}
    with pytest.raises(SystemExit):
        dr.parse_pr_urls(["https://github.com/numpy/numpy/issues/1"])


def test_default_registry(monkeypatch, tmp_path):
    p = tmp_path / "reg.csv"
    p.write_text("library,repo\n")
    monkeypatch.setenv("POC_REGISTRY", str(p))
    assert dr.default_registry() == str(p)
    rows = list(__import__("csv").DictReader(open(ROOT / "ops" / "tracked-libraries.csv")))
    assert {r["repo"] for r in rows} == {"numpy/numpy", "pandas-dev/pandas", "scikit-learn/scikit-learn"}
