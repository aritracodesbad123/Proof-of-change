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


def test_golden_sklearn_import_failure(imblearn):
    c = case("golden-sklearn160rc1-imblearn-import-failure")
    assert check_golden_case(imblearn, c).status == "pass"
    r = copy.deepcopy(imblearn)
    r["classification"]["import_failure"] = 0
    assert check_golden_case(r, c).status == "fail"


def test_golden_clean_pair_logic(upset):
    c = copy.deepcopy(case("golden-clean-pair-zero-breaks"))
    r = copy.deepcopy(upset)
    for k in r["classification"]:
        r["classification"][k] = 0
    assert check_golden_case(r, c).status == "pass"
    r["classification"]["real_break"] = 1
    assert check_golden_case(r, c).status == "fail"


def test_golden_coverage_todo_not_fail(ci_records):
    cov = {x.check.split(":")[1]: x.status for x in golden_coverage(ci_records)}
    assert cov["golden-clean-pair-zero-breaks"] == "todo"
    assert cov["golden-pandas300rc0-upsetplot-cow"] == "pass"


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
    assert run_evals.main(["--observations", str(obs), "--out", str(out)]) == 0
    ev = json.loads(out.read_text())
    assert ev["recommendation"] == "APPROVE"
    assert "fail" not in ev["counts"]


def test_strict_mode_rejects_legacy(tmp_path):
    from pathlib import Path
    obs = Path(__file__).parent / "fixtures" / "observations_legacy.jsonl"
    assert run_evals.main(["--observations", str(obs), "--out", str(tmp_path / "e.json")]) == 1
    assert run_evals.main(["--observations", str(obs), "--legacy", "--out", str(tmp_path / "e.json")]) == 0


def test_recommendation():
    from evals.checks import Result
    assert recommendation([Result("a", "pass", ""), Result("b", "warn", "")]) == "APPROVE"
    assert recommendation([Result("a", "fail", "")]) == "REJECT"
