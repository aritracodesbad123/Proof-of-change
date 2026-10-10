"""Verdicts when tests did not actually run: modules that fail to load, all-skipped runs, environment-prefixed
collection-error ids, one-side load failures, the changed module's own tests; plus run_date, records/report agreement
and verification records (schema rev 5)."""
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from ops.daily_run import (
    compare_sides,
    exit_check,
    migrate_record,
    parse_junit,
    pick_verification_file,
    read_verification,
    report_only,
    run_date_for,
    verdict_for,
)
from poc import coverage_gate

FIX = Path(__file__).parent / "fixtures" / "load_failures"
SCHEMA = json.loads((Path(__file__).parent.parent / "harness" / "schema" / "observation.schema.json").read_text())

P, F, E, S = ("passed", ""), ("failed", "assert"), ("load_error", "collection failure"), ("skipped", "Skipped: x")
U = "::tests.test_mod"


def judge(main: dict, pr: dict, files: dict | None = None, flaky_pr: dict | None = None):
    res = {"main": [main] * 3, "pr": [pr] * 3 if not flaky_pr else [pr, flaky_pr, pr]}
    cmp = compare_sides(res)
    return cmp, verdict_for(cmp, None, None, files)


def final(main, pr, files=None, coverage=None):
    """Verdict after the coverage gate, as stored in records.jsonl."""
    cmp, (v, reason, _) = judge(main, pr, files)
    rec = {"verdict": v, "reason": reason, "files": files or {"all": ["pkg/mod.py"]}, "coverage": coverage or {}}
    return coverage_gate.apply(rec)["verdict"]


# ---------------------------------------------------------------- (a) the real xarray#11663 run
def test_xarray_11663_both_modules_fail_to_load_is_could_not_verify():
    d = FIX / "xarray-11663"
    meta = json.loads((d / "meta.json").read_text())
    res = {s: [parse_junit(d / f"junit-{s}-{i}.xml") for i in (1, 2, 3)] for s in ("main", "pr")}
    cmp = compare_sides(res)
    v, reason, findings = verdict_for(cmp, None, exit_check(meta["per_run"], res, cmp), meta["files"])
    assert v == "could_not_verify"
    assert cmp["executed"] == {"main": 0, "pr": 0} and cmp["same"] == 0
    assert cmp["load_failed_both"] == ["xarray.tests.backends.test_datatree", "xarray.tests.backends.test_zarr"]
    assert reason.startswith("no test actually ran on either side") and "0 tests ran" in reason
    assert "2 unchanged" not in reason and "0 unchanged" in reason   # modules that failed to load are not "unchanged"
    assert "no_difference" not in findings


# ---------------------------------------------------------------- (b) every test skipped
@pytest.mark.parametrize("main,pr", [
    ({"t::a": S, "t::b": S}, {"t::a": S, "t::b": S}),                 # all skipped on both sides
    ({U: E, "t::a": S}, {U: E, "t::a": S}),                           # uncollected + the rest skipped
    ({"t::a": P, "t::b": P}, {"t::a": S, "t::b": S}),                 # every test skipped on the PR side
])
def test_nothing_executed_is_could_not_verify(main, pr):
    cmp, (v, reason, findings) = judge(main, pr)
    assert v == "could_not_verify" and reason.startswith("no test actually ran")
    assert "no_difference" not in findings


def test_all_skipped_reason_says_so():
    _, (_, reason, _) = judge({"t::a": S}, {"t::a": S})
    assert "0 tests ran" in reason and "1 unchanged (1 of them skipped on both sides)" in reason


def test_all_skipped_stays_could_not_verify_after_the_gate():
    assert final({"t::a": S}, {"t::a": S}, coverage={"status": "failed"}) == "could_not_verify"
    assert final({"t::a": S}, {"t::a": S}, coverage={"status": "measured", "changed_lines_total": 10,
                                                      "changed_lines_covered": 10}) == "could_not_verify"


# ---------------------------------------------------------------- (c) environment-prefixed collection-error ids
def _junit(path: Path, cases: list[tuple[str, str, str | None]]) -> Path:
    body = "".join(f'<testcase classname="{c}" name="{n}">' + ('<error message="collection failure">x</error>' if o == "error"
                   else "") + "</testcase>" for c, n, o in cases)
    path.write_text(f'<?xml version="1.0"?><testsuites><testsuite name="pytest">{body}</testsuite></testsuites>')
    return path


def test_nightly_collection_error_ids_are_side_independent(tmp_path):
    m = _junit(tmp_path / "m.xml", [("", "ops.work.pkg-1.venv-main.lib.python3.12.site-packages.pkg.tests.test_broken", "error")])
    p = _junit(tmp_path / "p.xml", [("", "ops.work.pkg-1.venv-pr.lib.python3.12.site-packages.pkg.tests.test_broken", "error")])
    assert list(parse_junit(m)) == list(parse_junit(p)) == ["::pkg.tests.test_broken"]
    assert parse_junit(m)["::pkg.tests.test_broken"][0] == "load_error"
    cmp, (v, reason, _) = judge(parse_junit(m), parse_junit(p))
    assert v == "could_not_verify"            # not needs_attention ("1 removed + 1 new failing")
    assert cmp["removed_tests"] == [] and cmp["new_tests_failing"] == [] and cmp["load_failed_both"] == ["pkg.tests.test_broken"]


def test_prefixed_ids_from_the_review_are_matched():
    a = {"::main.lib.site-packages.pkg.tests.test_broken": E}
    b = {"::pr.lib.site-packages.pkg.tests.test_broken": E}
    # parse_junit normalizes; the dict form is what it produces after normalization
    from ops.daily_run import side_independent
    a = {"::" + side_independent(k[2:]): v for k, v in a.items()}
    b = {"::" + side_independent(k[2:]): v for k, v in b.items()}
    assert a.keys() == b.keys()
    assert judge(a, b)[1][0] == "could_not_verify"


def test_nightly_normal_test_ids_unchanged(tmp_path):
    j = _junit(tmp_path / "j.xml", [("x.venv-main.lib.python3.12.site-packages.pkg.tests.test_a", "test_x", None)])
    assert list(parse_junit(j)) == ["pkg.tests.test_a::test_x"]


# ---------------------------------------------------------------- (d) uncollected + a real regression
def test_uncollected_plus_regression_is_needs_attention():
    cmp, (v, reason, _) = judge({U: E, "t::a": P}, {U: E, "t::a": F})
    assert v == "needs_attention" and "pass on main but fail on the PR" in reason


def test_one_side_load_failure_plus_regression_is_needs_attention():
    _, (v, _, _) = judge({"t::a": P, "tests.test_mod::x": P}, {"t::a": F, U: E})
    assert v == "needs_attention"


# ---------------------------------------------------------------- one-side load failure (names the module)
def test_module_fails_to_load_on_pr_side_only():
    main = {"t::a": P, "tests.test_mod::x": P, "tests.test_mod.TestC::y": P}
    cmp, (v, reason, _) = judge(main, {"t::a": P, U: E})
    assert v == "could_not_verify"
    assert reason.startswith("test module tests.test_mod fails to load on the PR side (2 test(s) no longer run)")
    assert cmp["removed_tests"] == [] and cmp["load_failed_pr"] == [{"module": "tests.test_mod", "tests_affected": 2}]


def test_module_fails_to_load_on_main_only():
    cmp, (v, reason, _) = judge({"t::a": P, U: E}, {"t::a": P, "tests.test_mod::x": P})
    assert v == "could_not_verify" and reason.startswith("test module tests.test_mod fails to load on the main side")
    assert cmp["new_tests_passing"] == 0


# ---------------------------------------------------------------- the changed module's own tests
def test_touched_module_tests_fail_to_load_unrelated_pass_is_not_verified():
    files = {"all": ["pkg/mod.py"], "package_py": ["pkg/mod.py"], "compiled": [], "other": []}
    _, (v, reason, _) = judge({U: E, "t::a": P}, {U: E, "t::a": P}, files)
    assert v == "could_not_verify" and "tests.test_mod" in reason and "failed to load on both sides" in reason
    assert final({U: E, "t::a": P}, {U: E, "t::a": P}, files,
                 {"status": "measured", "changed_lines_total": 10, "changed_lines_covered": 10}) == "could_not_verify"


def test_changed_test_file_that_fails_to_load_is_not_verified():
    files = {"all": ["pkg/other.py", "tests/test_mod.py"]}
    assert judge({U: E, "t::a": P}, {U: E, "t::a": P}, files)[1][0] == "could_not_verify"


def test_unrelated_module_failing_to_load_on_both_sides_still_verifies():
    files = {"all": ["pkg/other.py"]}
    _, (v, reason, findings) = judge({U: E, "t::a": P}, {U: E, "t::a": P}, files)
    assert v == "verified" and "1 test module(s) fail to load on both sides (tests.test_mod)" in reason
    assert "1 unchanged" in reason and "no_difference" in findings


# ---------------------------------------------------------------- reason text
def test_reason_mentions_flaky_tests():
    _, (v, reason, _) = judge({"t::a": P, "t::b": P}, {"t::a": P, "t::b": P}, flaky_pr={"t::a": P, "t::b": F})
    assert "1 flaky test(s)" in reason


def test_reason_counts_tests_that_ran():
    _, (_, reason, _) = judge({"t::a": P, "t::b": S}, {"t::a": P, "t::b": S, "t::c": P})
    assert "1 test(s) ran on main, 2 on the PR" in reason


# ---------------------------------------------------------------- run_date
@pytest.mark.parametrize("folder,expected", [("2026-10-10", "2026-10-10"), ("2026-10-10/incremental-1130", "2026-10-10"),
                                             ("2026-10-10-check-0930", "2026-10-10")])
def test_run_date_is_a_calendar_date(tmp_path, folder, expected):
    assert run_date_for(tmp_path / folder) == expected


def test_migrate_repairs_truncated_run_date(tmp_path):
    rec = {"record_kind": "pr_run", "run_date": "incrementa", "date_ist": "2026-10-10 11:24 IST", "verdict": "verified",
           "reason": "x"}
    assert migrate_record(rec, tmp_path / "incremental-1130")["run_date"] == "2026-10-10"


# ---------------------------------------------------------------- records.jsonl agrees with the report
def _run_folder(tmp_path: Path) -> Path:
    rdir = tmp_path / "2026-10-10" / "incremental-1130"
    shutil.copytree(FIX / "xarray-11663", rdir / "xarray-11663")
    meta = json.loads((FIX / "xarray-11663" / "meta.json").read_text())
    base = {"schema_version": "1", "record_kind": "pr_run", "run_date": "incrementa", "date_ist": "2026-10-10 11:24 IST",
            "verdict": "verified", "runs_per_side": 3, "author": "a", "updated_at_ist": "u", "ci_state": "success",
            "ci_detail": "d", "tested_at_ist": "2026-10-10 11:24 IST", "duration_s": {"total_wall": 1.0},
            "tested": {"main": "main", "pr": "pr"}}
    recs = [base | {"repo": "pydata/xarray", "pr": {"number": 11663, "url": "u", "title": "t", "head_sha": "a" * 40},
                    "route": "source-pair",
                    "logs": "xarray-11663/", "files": meta["files"], "per_run": meta["per_run"],
                    "comparison": {"same": 2, "skipped_missing_dependency": []}, "reason": "0 new test(s) pass, 2 unchanged",
                    "coverage": {"status": "measured", "changed_lines_total": 0, "changed_lines_covered": 0}},
            base | {"repo": "numpy/numpy", "pr": {"number": 32910, "url": "u", "title": "t", "head_sha": "b" * 40}, "route": "source-build",
                    "files": {"all": ["numpy/_core/src/x.c"], "package_py": [], "compiled": ["numpy/_core/src/x.c"],
                              "other": []}, "per_run": [], "reason": "3 unchanged"}]
    (rdir / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    (rdir / "xarray-11663" / "record.json").write_text(json.dumps(recs[0]))
    (rdir / "run_meta.json").write_text(json.dumps({"date": "incremental-1130", "started_ist": "s", "finished_ist": "f",
                                                    "wall_min": 1, "runs": 3, "machine": "m", "api_calls": 0, "auth": "x"}))
    (rdir / "selection.json").write_text(json.dumps({"selected": {}, "skipped": {}}))
    return rdir


def _args(tmp_path, rejudge):
    return SimpleNamespace(rejudge=rejudge, no_report=True, report_dir=None, chosen_prs=str(tmp_path / "none.md"),
                           verification=str(tmp_path / "none.jsonl"), libraries_file=str(tmp_path / "libs.csv"))


def _report_verdicts(rdir: Path) -> dict:
    out = {}
    for ln in (rdir / "REPORT.md").read_text().splitlines():
        if ln.startswith("| ["):
            key = ln.split("[", 1)[1].split("]", 1)[0]
            out[key] = ln.split("**")[1]
    return out


@pytest.mark.parametrize("rejudge", [False, True])
def test_records_jsonl_record_json_and_report_agree(tmp_path, rejudge):
    rdir = _run_folder(tmp_path)
    assert report_only(rdir, _args(tmp_path, rejudge)) == 0
    recs = [json.loads(ln) for ln in (rdir / "records.jsonl").read_text().splitlines()]
    stored = {f"{r['repo']}#{r['pr']['number']}": r["verdict"] for r in recs}
    assert stored == _report_verdicts(rdir)
    assert stored["numpy/numpy#32910"] == "could_not_verify"           # final verdict after the coverage gate
    assert all(r["run_date"] == "2026-10-10" for r in recs)
    assert json.loads((rdir / "xarray-11663" / "record.json").read_text())["verdict"] == stored["pydata/xarray#11663"]
    assert (rdir / "pre-migration" / "records.jsonl").exists()
    if rejudge:
        x = next(r for r in recs if r["repo"] == "pydata/xarray")
        assert x["verdict"] == "could_not_verify" and x["rejudged"]["previous_verdict"] == "verified"
    before = (rdir / "records.jsonl").read_text()
    report_only(rdir, _args(tmp_path, rejudge))                        # idempotent
    assert (rdir / "records.jsonl").read_text() == before


# ---------------------------------------------------------------- verification records (schema rev 5)
def _verification(checker_verdict, status, under_review="verified", repo="o/r", pr=7):
    return {"schema_version": "1", "record_kind": "verification", "id": f"verif-{repo.replace('/', '-')}-{pr}",
            "date_ist": "2026-10-10 06:25 IST", "who": "checker",
            "verification": {"checker": {"name": "checker"},
                             "target": {"record_id": f"pr-o-r-{pr}-0123456789ab-2026-10-10", "repo": repo, "pr_number": pr,
                                        "head_sha": "0123456789abcdef0123456789abcdef01234567"},
                             "verdict_under_review": {"verdict": under_review, "as_of": "report, 06:12 IST"},
                             "checker_verdict": checker_verdict, "check_status": status,
                             "evidence": [{"kind": "rerun", "detail": "3+3 runs"}]}}


def test_scorer_reads_checker_verdict_never_the_verdict_under_review(tmp_path):
    f = tmp_path / "verification.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in (
        _verification("needs_attention", "mismatch", "verified", pr=1),
        _verification(None, "unverified", "could_not_verify", pr=2),          # only the run's verdict: not scored
        _verification("verified", "verified_by_checker", "verified", pr=3))))
    got = read_verification(f)
    assert {k: v[0] for k, v in got.items()} == {("o/r", 1): "needs_attention", ("o/r", 3): "verified"}


def test_verification_record_validates_and_wrong_shapes_do_not():
    from guardrails.schema import validate_record
    from ops.schema_check import validate
    ok = _verification("needs_attention", "mismatch")
    assert validate(ok, SCHEMA) == [] and validate_record(ok) == []
    bad = json.loads(json.dumps(ok)); bad["verification"]["checker_verdict"] = "needs attention"
    assert validate(bad, SCHEMA)
    bad = json.loads(json.dumps(ok)); del bad["verification"]["verdict_under_review"]
    assert validate(bad, SCHEMA)
    bad = json.loads(json.dumps(ok)); del bad["verification"]
    assert validate(bad, SCHEMA)
    assert "verdict" not in SCHEMA["properties"]["verification"]["properties"]   # no ambiguous top-level verdict


def test_rev5_keeps_observation_required_fields():
    from guardrails.schema import REQUIRED
    assert "classification" in REQUIRED and "accepted" in REQUIRED


def test_pick_verification_file_prefers_rev5_records(tmp_path):
    (tmp_path / "verification.jsonl").write_text(json.dumps({"repo": "o/r", "pr": 1, "verdict": "verified"}) + "\n")
    assert pick_verification_file(tmp_path).name == "verification.jsonl"
    (tmp_path / "verification.v2.jsonl").write_text(json.dumps(_verification("verified", "verified_by_checker")) + "\n")
    assert pick_verification_file(tmp_path).name == "verification.v2.jsonl"
    assert pick_verification_file(tmp_path / "missing").name == "verification.jsonl"
