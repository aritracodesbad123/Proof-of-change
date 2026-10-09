import copy
import json

from evals import run_evals
from evals.checks import (
    check_citations,
    check_golden_case,
    check_runs_per_side,
    check_single_thread,
    check_versions,
    evaluate_record,
    golden_coverage,
    load_golden,
    recommendation,
)

FIXLOGS = __import__("pathlib").Path(__file__).parent / "fixtures" / "run-logs" / "demo"


def case(name):
    return next(c for c in load_golden() if c["name"] == name)


def test_real_records_pass_core_checks(ci_records):
    for r in ci_records:
        st = {x.check: x.status for x in evaluate_record(r)}
        assert st["schema"] == "pass"
        assert st["versions_installed"] == "pass"
        assert st["runs_per_side"] == "pass"
        assert st["single_thread"] == "pass"
        assert st["llm_citations"] == "skip"


def test_versions_wrong_install(upset):
    r = copy.deepcopy(upset)
    r["new_version"] = "2.3.3"
    assert check_versions(r).status == "fail"
    r = copy.deepcopy(upset)
    r["env_diff"].append("numpy==2.3.5")
    assert check_versions(r).status == "fail"


def test_runs_per_side_enforced(upset):
    r = copy.deepcopy(upset)
    r["per_run"] = r["per_run"][:4]
    assert check_runs_per_side(r).status == "fail"
    r = copy.deepcopy(upset)
    r["per_run"] = sorted(r["per_run"], key=lambda x: x["side"])  # not alternating
    assert check_runs_per_side(r).status == "fail"
    r = copy.deepcopy(upset)
    r["per_run"][1]["exit"] = "timeout"
    assert check_runs_per_side(r).status == "fail"


def test_single_thread(upset):
    r = copy.deepcopy(upset)
    r["thread_env"]["OMP_NUM_THREADS"] = "8"
    assert check_single_thread(r).status == "fail"
    del r["thread_env"]
    assert check_single_thread(r).status == "warn"


def test_golden_upsetplot_exact(upset):
    c = case("golden-pandas300rc0-upsetplot-cow")
    assert check_golden_case(upset, c).status == "pass"
    r = copy.deepcopy(upset)
    r["classification"]["real_break"] = 66  # one known break missed
    assert check_golden_case(r, c).status == "fail"


def test_golden_sklearn_raw_repro_passes(imblearn):
    from conftest import FIXTURE_RUNS
    res = {x.check: x for x in evaluate_record(imblearn, FIXTURE_RUNS)}
    g = "golden:golden-sklearn160rc1-imblearn-import-failure"
    assert res[g].status == "pass", res[g].detail
    assert res[g + ":import_message"].status == "pass"
    assert "pytest-new-1.log" in res[g + ":import_message"].detail  # found via the logs, not the record


def test_golden_sklearn_gates_fail_on_miscounted_dev_record(dev_imblearn):
    c = case("golden-sklearn160rc1-imblearn-import-failure")
    r = check_golden_case(dev_imblearn, c)
    assert r.status == "fail"
    assert "new run 1: pytest says passed=250 (gate 0)" in r.detail
    assert "old run 1: pytest says passed=2239 (gate 2238)" in r.detail
    assert "errors=13 (gate 525)" in r.detail


def test_golden_sklearn_new_side_must_have_zero_passed(imblearn):
    c = case("golden-sklearn160rc1-imblearn-import-failure")
    r = copy.deepcopy(imblearn)
    r["per_run"][3]["pytest_summary"] = "1 passed, 524 errors in 7.0s"
    assert check_golden_case(r, c).status == "fail"


def test_import_message_check_sources(imblearn, tmp_path):
    from evals.checks import check_import_message
    r = copy.deepcopy(imblearn)
    assert check_import_message(r, "_safe_tags", None, "g").status == "skip"  # no field, no signature, no logs
    r["import_failure_messages"] = ["ImportError: cannot import name '_safe_tags' from 'sklearn.utils._tags'"]
    assert check_import_message(r, "_safe_tags", None, "g").status == "pass"
    r["import_failure_messages"] = ["ImportError: cannot import name 'foo'"]
    assert check_import_message(r, "_safe_tags", None, "g").status == "fail"
    del r["import_failure_messages"]
    for n in (1, 2, 3):
        (tmp_path / f"pytest-new-{n}.log").write_text("E   ImportError: cannot import name 'other'\n")
    assert check_import_message(r, "_safe_tags", tmp_path, "g").status == "fail"


def test_parse_pytest_summary():
    from evals.checks import parse_pytest_summary
    assert parse_pytest_summary("2238 passed, 33 skipped, 1 xfailed, 5 xpassed, 118 warnings in 25.26s") == \
        {"passed": 2238, "skipped": 33, "xfailed": 1, "xpassed": 5}
    assert parse_pytest_summary("525 errors in 9.67s") == {"errors": 525}
    assert parse_pytest_summary("1 failed, 1 error in 1s") == {"failed": 1, "errors": 1}


def test_clean_pair_candidate_is_pending_and_only_warns(imblearn):
    c = case("candidate-clean-pair-sklearn151-152-imblearn")
    assert c["status"] == "pending"
    r = copy.deepcopy(imblearn)
    r["old_version"], r["new_version"] = "1.5.1", "1.5.2"
    for k in r["classification"]:
        r["classification"][k] = 0
    assert check_golden_case(r, c).status == "pass"
    r["classification"]["real_break"] = 1
    assert check_golden_case(r, c).status == "warn"  # not golden yet: never fails a run


def test_golden_coverage_modes(ci_records):
    cov = {x.check.split(":")[1]: x.status for x in golden_coverage(ci_records, require=True)}
    assert cov["candidate-clean-pair-sklearn151-152-imblearn"] == "todo"
    assert cov["golden-pandas300rc0-upsetplot-cow"] == "pass"
    assert cov["golden-sklearn160rc1-imblearn-import-failure"] == "pass"
    upset_only = [r for r in ci_records if r["dependent"] == "UpSetPlot"]
    req = {x.check.split(":")[1]: x.status for x in golden_coverage(upset_only, require=True)}
    daily = {x.check.split(":")[1]: x.status for x in golden_coverage(upset_only, require=False)}
    assert req["golden-sklearn160rc1-imblearn-import-failure"] == "fail"
    assert daily["golden-sklearn160rc1-imblearn-import-failure"] == "skip"


def test_citations():
    good = [{"text": "CoW breaks plotting", "citations": [{"file": "pytest-new-1.log", "line": 4, "quote": "Invalid RGBA argument: nan"}]}]
    assert check_citations(good, FIXLOGS).status == "pass"
    for bad in (
        [{"text": "uncited"}],
        [{"text": "x", "citations": [{"file": "pytest-new-1.log", "line": 4, "quote": "made up"}]}],
        [{"text": "x", "citations": [{"file": "pytest-new-1.log", "line": 99, "quote": "nan"}]}],
        [{"text": "x", "citations": [{"file": "../../../conftest.py", "line": 1, "quote": "import"}]}],
        [{"text": "x", "citations": [{"file": "missing.log", "line": 1, "quote": "a"}]}],
    ):
        assert check_citations(bad, FIXLOGS).status == "fail"


def test_run_evals_cli(tmp_path, ci_records):
    obs = tmp_path / "obs.jsonl"
    obs.write_text("\n".join(json.dumps(r) for r in ci_records) + "\n")
    out = tmp_path / "ev.json"
    from conftest import FIXTURE_RUNS
    assert run_evals.main(["--observations", str(obs), "--runs-root", str(FIXTURE_RUNS), "--require-golden",
                           "--out", str(out)]) == 0
    ev = json.loads(out.read_text())
    assert ev["recommendation"] == "APPROVE"
    assert "fail" not in ev["counts"]


def test_strict_mode_rejects_legacy(tmp_path):
    from pathlib import Path
    obs = Path(__file__).parent / "fixtures" / "observations_legacy.jsonl"
    assert run_evals.main(["--observations", str(obs), "--out", str(tmp_path / "e.json")]) == 1
    # even without the strict fields, the dev sklearn record fails the raw-reproduction gates
    assert run_evals.main(["--observations", str(obs), "--legacy", "--out", str(tmp_path / "e.json")]) == 1


def test_recommendation():
    from evals.checks import Result
    assert recommendation([Result("a", "pass", ""), Result("b", "warn", "")]) == "APPROVE"
    assert recommendation([Result("a", "fail", "")]) == "REJECT"
