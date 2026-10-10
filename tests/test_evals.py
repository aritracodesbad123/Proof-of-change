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


def test_golden_upsetplot_exact(g_pandas):
    c = case("golden-pandas300rc0-upsetplot-cow")
    assert c["status"] == "active"
    assert (c["expect"]["exact"]["real_break"], c["expect"]["exact"]["already_broken"]) == (67, 6)
    assert check_golden_case(g_pandas, c).status == "pass"
    r = copy.deepcopy(g_pandas)
    r["classification"]["real_break"] = 66  # one known break missed
    assert check_golden_case(r, c).status == "fail"


def test_golden_v1_records_pass_all_evals(golden_v1_records):
    for r in golden_v1_records:
        res = evaluate_record(r, require_v1=True)
        assert recommendation(res) == "APPROVE", [x for x in res if x.status == "fail"]
        assert {x.check: x.status for x in res}["schema"] == "pass"
    golden = [x for r in golden_v1_records for x in evaluate_record(r) if x.check.startswith("golden:")]
    assert len(golden) == 4 and all(x.status == "pass" for x in golden)  # 3 cases + the _safe_tags message check


def test_golden_sklearn_exact_classification(g_sklearn):
    c = case("golden-sklearn160rc1-imblearn-import-failure")
    assert c["status"] == "active" and "todo" not in c
    assert c["expect"]["exact"] == {"real_break": 0, "already_broken": 0, "flaky": 0, "import_failure": 46,
                                    "fixed_by_new": 0, "lost_tests": 2243}
    assert check_golden_case(g_sklearn, c).status == "pass"
    r = copy.deepcopy(g_sklearn)
    r["classification"]["real_break"], r["classification"]["lost_tests"] = 280, 1963  # importlib-mode artefact
    assert check_golden_case(r, c).status == "fail"


def test_collection_errors_counted_per_module_not_per_test(imblearn):
    # the pre-v1 CI fixture's placeholder counted every one of the 525 errors as an import failure
    assert imblearn["classification"]["import_failure"] == 525
    r = check_golden_case(imblearn, case("golden-sklearn160rc1-imblearn-import-failure"))
    assert r.status == "fail" and "import_failure=525 (expected exactly 46)" in r.detail


def test_import_message_found_in_raw_logs(imblearn):
    from conftest import FIXTURE_RUNS
    res = {x.check: x for x in evaluate_record(imblearn, FIXTURE_RUNS)}
    m = res["golden:golden-sklearn160rc1-imblearn-import-failure:import_message"]
    assert m.status == "pass" and "pytest-new-1.log" in m.detail  # found via the logs, not the record


def test_import_message_ignores_pytest_E_prefix(g_sklearn, tmp_path):
    from evals.checks import check_import_message, is_import_error_mentioning, normalise_error_line
    raw = "E   ImportError: cannot import name '_safe_tags' from 'sklearn.utils._tags' (<path>"
    assert normalise_error_line(raw).startswith("ImportError: cannot import name '_safe_tags'")
    assert normalise_error_line("  E\tImportError: x  ") == "ImportError: x"
    assert normalise_error_line("Error: E is not a prefix here") == "Error: E is not a prefix here"
    for line in (raw, raw[4:], "  " + raw, "package import imblearn: " + raw[4:]):
        assert is_import_error_mentioning(line, "_safe_tags")
    assert not is_import_error_mentioning("E   AttributeError: _safe_tags", "_safe_tags")
    # the record's top signature starts with 'E   '; with the import probe removed it must still match on content
    r = copy.deepcopy(g_sklearn)
    del r["dependent_import"]
    r["top_error_signatures_breaks"] = [[raw, 505]]
    res = check_import_message(r, "_safe_tags", None, "g")
    assert res.status == "pass" and "break signature (ImportError: cannot import name '_safe_tags'" in res.detail
    r["import_failure_messages"] = [raw]
    assert check_import_message(r, "_safe_tags", None, "g").status == "pass"
    # logs with and without the E prefix
    del r["import_failure_messages"]
    r["top_error_signatures_breaks"] = []
    for n in (1, 2, 3):
        (tmp_path / f"pytest-new-{n}.log").write_text(("noise\n" + raw[4:] + "\n") if n == 2 else (raw + "\n"))
    assert check_import_message(r, "_safe_tags", tmp_path, "g").status == "pass"


def test_golden_signature_contains_matches_content(g_sklearn):
    c = case("golden-sklearn160rc1-imblearn-import-failure")
    r = copy.deepcopy(g_sklearn)
    r["top_error_signatures_breaks"] = [["E   ImportError: cannot import name '_safe_tags' from 'sklearn.utils._tags' (<path>", 525]]
    assert check_golden_case(r, c).status == "pass"


def test_summary_counts_cross_checked(g_sklearn):
    c = case("golden-sklearn160rc1-imblearn-import-failure")
    r = copy.deepcopy(g_sklearn)
    r["per_run"][1]["summary_counts"] = {"error": 524}
    res = check_golden_case(r, c)
    assert res.status == "fail" and "disagree with pytest_summary" in res.detail


def test_golden_sklearn_gates_fail_on_miscounted_dev_record(dev_imblearn):
    c = case("golden-sklearn160rc1-imblearn-import-failure")
    r = check_golden_case(dev_imblearn, c)
    assert r.status == "fail"
    assert "new run 1: pytest says passed=250 (gate 0)" in r.detail
    assert "old run 1: pytest says passed=2239 (gate 2238)" in r.detail
    assert "errors=13 (gate 525)" in r.detail


def test_golden_sklearn_new_side_must_have_zero_passed(g_sklearn):
    c = case("golden-sklearn160rc1-imblearn-import-failure")
    r = copy.deepcopy(g_sklearn)
    r["per_run"][3]["pytest_summary"] = "1 passed, 524 errors in 7.0s"
    r["per_run"][3]["summary_counts"] = {"passed": 1, "error": 524}
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


def test_clean_pair_promoted_to_golden(g_clean):
    c = case("golden-clean-sklearn151-152-imblearn")
    assert c["status"] == "active"
    assert all(v == 0 for v in c["expect"]["exact"].values()) and len(c["expect"]["exact"]) == 6
    assert check_golden_case(g_clean, c).status == "pass"
    r = copy.deepcopy(g_clean)
    r["classification"]["real_break"] = 1
    assert check_golden_case(r, c).status == "fail"  # now golden: a false alarm fails the run
    assert not any(x["name"].startswith("candidate-") for x in load_golden())


def test_golden_coverage_modes(golden_v1_records, ci_records):
    from evals.checks import GOLDEN_PR_BATCH
    pr_records = [json.loads(x) for x in GOLDEN_PR_BATCH.read_text().splitlines() if x.strip()]
    cov = {x.check.split(":")[1]: x.status for x in golden_coverage(golden_v1_records + pr_records, require=True)}
    assert cov == {"golden-sklearn160rc1-imblearn-import-failure": "pass", "golden-pandas300rc0-upsetplot-cow": "pass",
                   "golden-clean-sklearn151-152-imblearn": "pass", "golden-pr-mlxtend-1229-probe": "pass"}
    only_v1 = {x.check.split(":")[1]: x.status for x in golden_coverage(golden_v1_records, require=True)}
    assert only_v1["golden-pr-mlxtend-1229-probe"] == "fail"   # the golden PR case is required in a golden batch
    req = {x.check.split(":")[1]: x.status for x in golden_coverage(ci_records, require=True)}
    assert req["golden-clean-sklearn151-152-imblearn"] == "fail"  # pre-v1 CI fixtures no longer cover every case
    upset_only = [r for r in golden_v1_records if r["dependent"] == "UpSetPlot"]
    daily = {x.check.split(":")[1]: x.status for x in golden_coverage(upset_only, require=False)}
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


def test_run_evals_cli_golden_strict(tmp_path):
    from conftest import REPO
    out = tmp_path / "ev.json"
    assert run_evals.main(["--observations", str(REPO / "evals" / "fixtures" / "golden_v1.jsonl"), "--require-golden",
                           "--require-v1", "--out", str(out)]) == 0
    ev = json.loads(out.read_text())
    assert ev["recommendation"] == "APPROVE" and ev["require_v1"] is True
    assert "fail" not in ev["counts"]
    assert ev["pr_observations"].endswith("golden_pr_v1.jsonl")            # the golden PR batch is folded in
    assert [r["recommendation"] for r in ev["pr_records"]] == ["APPROVE"]
    assert {"golden-coverage:golden-pr-mlxtend-1229-probe"} <= {x["check"] for x in ev["golden_coverage"]
                                                                 if x["status"] == "pass"}


def test_run_evals_cli_rejects_pre_v1_golden_batch(tmp_path, ci_records):
    obs = tmp_path / "obs.jsonl"
    obs.write_text("\n".join(json.dumps(r) for r in ci_records) + "\n")
    assert run_evals.main(["--observations", str(obs), "--require-golden", "--require-v1",
                           "--out", str(tmp_path / "e.json")]) == 1


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
