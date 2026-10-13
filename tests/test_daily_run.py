import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("daily_run", ROOT / "ops" / "daily_run.py")
dr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dr)

CHOSEN = """# chosen PRs
## 1. demo
- **Repo:** https://github.com/acme/widget (default branch `main`)
- **Open PR:** #12, "Fix thing"
  - Head SHA: `0123456789abcdef0123456789abcdef01234567`
**Expected Proof-of-Change verdict: `needs attention` (low severity)**
- Install: `pip install -e ".[x]" pytest hypothesis`
- Test (subset, fast): `pytest tests/test_a.py tests/test_b.py -n 4 -k "not slow"`
"""


def test_parse_chosen_has_no_expectations(tmp_path):
    p = tmp_path / "p.md"; p.write_text(CHOSEN)
    chosen = dr.parse_chosen(p)
    pk = chosen["acme/widget"][0]
    assert pk["pr"] == 12 and pk["head_sha"].startswith("0123")
    assert "expected" not in str(pk).lower()  # expectations are never part of the test inputs
    assert dr.chosen_test_targets(pk) == ["tests/test_a.py", "tests/test_b.py"]
    assert dr.side_install_args(pk, Path("/c")) == (["-e", "/c[x]"], ["pytest", "hypothesis"])
    assert dr.read_expectations(p) == {("acme/widget", 12): "needs_attention"}


def test_score_expectation():
    assert dr.score_expectation("needs_attention", "verified") == "miss"
    assert dr.score_expectation("verified", "needs_attention") == "false alarm"
    assert dr.score_expectation("verified", "verified") == "match"
    assert dr.score_expectation("verified", "could_not_verify").startswith("not scored")


def test_classify_and_package_diff():
    fc = dr.classify_files(["numpy/lib/_x.py", "numpy/_core/src/a.c", "doc/x.rst", "pyproject.toml"], "numpy")
    assert fc["package_py"] == ["numpy/lib/_x.py"] and "numpy/_core/src/a.c" in fc["compiled"]
    diff = ("diff --git a/doc/x.rst b/doc/x.rst\n--- a\n+++ b\n"
            "diff --git a/numpy/lib/_x.py b/numpy/lib/_x.py\n--- a/numpy/lib/_x.py\n+++ b/numpy/lib/_x.py\n")
    assert dr.package_diff(diff, "numpy").startswith("diff --git a/numpy/lib/_x.py")
    assert dr.diff_files(diff) == ["doc/x.rst", "numpy/lib/_x.py"]


def test_compare_and_verdict():
    m = [{"t::a": ("passed", ""), "t::b": ("failed", "E"), "t::c": ("passed", "")}] * 3
    p = [{"t::a": ("failed", "boom"), "t::b": ("passed", ""), "t::c": ("passed", ""), "t::d": ("passed", "")}] * 3
    c = dr.compare_sides({"main": m, "pr": p})
    assert c["regressions"] == ["t::a"] and c["fixed"] == ["t::b"] and c["new_tests_passing"] == 1 and c["same"] == 1
    v, reason, _ = dr.verdict_for(c, None)
    assert v == "needs_attention" and "pass on main but fail on the PR" in reason
    ok = dr.compare_sides({"main": [{"t::c": ("passed", "")}] * 3, "pr": [{"t::c": ("passed", "")}] * 3})
    assert dr.verdict_for(ok, None)[0] == "verified"
    assert dr.verdict_for(None, "build failed")[0] == "could_not_verify"


def test_parse_junit_ids_are_side_independent(tmp_path):
    from ops.daily_run import parse_junit
    for side in ("main", "pr"):
        (tmp_path / f"{side}.xml").write_text(
            f'<testsuite><testcase classname="ops.work.x.venv-{side}.lib.python3.12.site-packages.numpy.tests.T" name="t"/></testsuite>')
    assert parse_junit(tmp_path / "main.xml") == parse_junit(tmp_path / "pr.xml")


def test_same_day_rerun_ignores_own_state():
    from ops.daily_run import baseline_for
    seen = {"last_run_utc": {"a/b": "2026-10-10T00:25:57Z"}, "prs": {"a/b": {"1": {"run": "2026-10-10"}, "2": {"run": "2026-10-09"}}}}
    prs, since = baseline_for(seen, "a/b", "2026-10-10")
    assert since is None and list(prs["a/b"]) == ["2"]
    prs, since = baseline_for(seen, "a/b", "2026-10-11")
    assert since == "2026-10-10T00:25:57Z" and set(prs["a/b"]) == {"1", "2"}


# ---------------------------------------------------------------- regression tests for the day-1 fixes
# Fixtures: real JUnit files of day 1 (ops/runs/2026-10-10/superseded/attempt-4), trimmed to the relevant testcases.
import json as _json  # noqa: E402
import zipfile as _zipfile  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

DAY1 = _Path(__file__).parent / "fixtures" / "day1"
SCHEMA = _json.loads((_Path(__file__).parent.parent / "harness" / "schema" / "observation.schema.json").read_text())


def _day1(case):
    from ops.daily_run import parse_junit
    res = {s: [parse_junit(DAY1 / case / f"junit-{s}-{i}.xml") for i in (1, 2, 3)] for s in ("main", "pr")}
    meta = _json.loads((DAY1 / case / "meta.json").read_text())
    per_run = [{"side": {"main": "old", "pr": "new"}.get(x["side"], x["side"]), "run": x["run"], "exit": x["exit"]}
               for x in meta["per_run"]]
    return res, per_run


def _verdict(case):
    from ops.daily_run import compare_sides, exit_check, verdict_for
    res, per_run = _day1(case)
    cmp = compare_sides(res)
    files = _json.loads((DAY1 / case / "meta.json").read_text()).get("files")
    return cmp, verdict_for(cmp, None, exit_check(per_run, res, cmp), files)


# fix 1: re-parametrized tests are not "removed"
def test_fix1_pandas_70520_min_count_renamed_not_removed():
    cmp, (v, reason, _) = _verdict("pandas-70520")
    assert cmp["removed_tests"] == []
    rp = {x["test"]: x for x in cmp["reparametrized"]}
    t = "tests.groupby.test_missing::test_min_count"
    assert t in rp and len(rp[t]["removed_ids"]) == 4 and all("-0-1.0]" in i for i in rp[t]["added_ids"])
    assert "re-parametrized" in reason and v != "needs_attention"


def test_fix1_sklearn_35114_categoricalnb_split_into_5_variants():
    cmp, (v, reason, _) = _verdict("sklearn-35114")
    assert cmp["removed_tests"] == []
    (rp,) = cmp["reparametrized"]
    assert rp["test"].endswith("::test_categoricalnb") and len(rp["removed_ids"]) == 1 and len(rp["added_ids"]) == 5
    assert v == "verified", reason


def test_fix1_truly_removed_test_still_flagged():
    from ops.daily_run import compare_sides, verdict_for
    main = {"m::test_gone[a]": ("passed", ""), "m::test_keep": ("passed", "")}
    pr = {"m::test_keep": ("passed", "")}
    cmp = compare_sides({"main": [main] * 3, "pr": [pr] * 3})
    assert cmp["removed_tests"] == ["m::test_gone[a]"] and cmp["reparametrized"] == []
    assert verdict_for(cmp, None, None)[0] == "needs_attention"


# fix 2: missing optional dependency -> could not verify, never needs attention
def test_fix2_pandas_70989_scipy_skips_are_could_not_verify():
    cmp, (v, reason, _) = _verdict("pandas-70989")
    assert {d["module"] for d in cmp["skipped_missing_dependency"]} == {"scipy"}
    assert v == "could_not_verify" and "scipy" in reason and reason.count("not installed") == 1


def test_fix2_pandas_70520_pyarrow_skips_are_could_not_verify_without_pyarrow():
    cmp, (v, reason, _) = _verdict("pandas-70520")
    assert {d["module"] for d in cmp["skipped_missing_dependency"]} == {"pyarrow"}
    assert v == "could_not_verify" and "pyarrow" in reason


def test_fix2_missing_dependency_messages():
    from ops.daily_run import missing_dependency
    assert missing_dependency("pytest.skip: Could not import 'scipy'") == "scipy"
    assert missing_dependency("pytest.skip: could not import 'pyarrow': No module named 'pyarrow'") == "pyarrow"
    assert missing_dependency("pytest.skip: requires pyarrow") == "pyarrow"
    assert missing_dependency("ModuleNotFoundError: No module named 'pandas'") == "pandas"
    assert missing_dependency("ImportError: No module named 'pandas.core'") == "pandas"
    assert missing_dependency("pytest.xfail: EA.fillna does not handle 'linear' method") is None
    assert missing_dependency("pytest.skip: not relevant on windows") is None


def test_fix2_regression_beats_dependency_skip():
    from ops.daily_run import compare_sides, verdict_for
    main = {"m::a": ("passed", ""), "m::b": ("passed", "")}
    pr = {"m::a": ("failed", "boom"), "m::b": ("skipped", "pytest.skip: Could not import 'scipy'")}
    v, reason, _ = verdict_for(compare_sides({"main": [main] * 3, "pr": [pr] * 3}), None, None)
    assert v == "needs_attention" and "scipy" in reason


def test_fix2_test_extras_added_to_install_spec(tmp_path):
    from ops.daily_run import with_test_extras
    (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n[project.optional-dependencies]\n'
                                             'testing=["pytest"]\ndocs=["sphinx"]\n')
    assert with_test_extras(["-e", f"{tmp_path}[io]"], tmp_path) == ["-e", f"{tmp_path}[io,testing]"]
    assert with_test_extras(["-e", str(tmp_path)], tmp_path) == ["-e", f"{tmp_path}[testing]"]


def test_fix2_pandas_config_installs_pyarrow_and_scipy():
    from ops.daily_run import LIBS
    assert {"pyarrow", "scipy"} <= set(LIBS["pandas-dev/pandas"]["optional_test_deps"])


# fix 3: pin the nightly
def test_fix3_nightly_commit_from_real_version_strings(tmp_path):
    from ops.daily_run import nightly_commit
    cfg = {"commit_expr": ""}
    assert nightly_commit("3.2.0.dev0+139.gff72b53688", tmp_path, cfg, {})[0] == "ff72b53688"
    assert nightly_commit("2.6.0.dev0+git20261006.286e698", tmp_path, cfg, {})[0] == "286e698"
    assert nightly_commit("1.10.dev0", tmp_path, cfg, {}) == (None, "not embedded in the wheel")


def test_fix3_nightly_wheel_chooses_newest_matching_wheel():
    from ops.daily_run import nightly_wheel
    html = ('<a href="/s/pandas/3.2.0.dev0+120.gaaaaaaa/pandas-3.2.0.dev0+120.gaaaaaaa-cp312-cp312-manylinux_2_28_x86_64.whl">x</a>'
            '<a href="/s/pandas/3.2.0.dev0+139.gff72b53688/pandas-3.2.0.dev0+139.gff72b53688-cp312-cp312-'
            'manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl">x</a>'
            '<a href="/s/pandas/3.2.0.dev0+139.gff72b53688/pandas-3.2.0.dev0+139.gff72b53688-cp313-cp313-manylinux_2_28_x86_64.whl">x</a>'
            '<a href="/s/pandas/3.2.0.dev0+150.gbbbbbbb/pandas-3.2.0.dev0+150.gbbbbbbb-cp312-cp312-macosx_11_0_arm64.whl">x</a>')
    w = nightly_wheel(lambda u: html.encode(), "pandas", "3.12")
    assert w["version"] == "3.2.0.dev0+139.gff72b53688" and "cp312" in w["filename"]


def test_fix3_fetch_wheel_hashes_and_dates(tmp_path):
    import hashlib

    from ops.daily_run import fetch_wheel
    whl = tmp_path / "src" / "x-1.0-cp312-cp312-manylinux_2_28_x86_64.whl"
    whl.parent.mkdir()
    with _zipfile.ZipFile(whl, "w") as z:
        z.writestr(_zipfile.ZipInfo("x/__init__.py", date_time=(2026, 10, 6, 3, 59, 0)), "")
    info = {"url": whl.as_uri(), "filename": whl.name, "version": "1.0"}
    m = fetch_wheel(info, tmp_path / "cache")
    assert m["sha256"] == hashlib.sha256(whl.read_bytes()).hexdigest()
    assert m["build_date_from_wheel"].startswith("2026-10-06 03:59")
    assert fetch_wheel(info, tmp_path / "cache")["sha256"] == m["sha256"]   # cached: same build for the whole run


# fix 4 + 5: merge commit recorded; pr_run records validate; old records still validate
def _pr_record(**kw):
    rec = {"schema_version": "1", "record_kind": "pr_run", "id": "pr-rasbt-mlxtend-1229-296459ec1712-2026-10-10",
           "date_ist": "2026-10-10 06:40 IST", "run_date": "2026-10-10", "who": "ops/daily_run.py", "repo": "rasbt/mlxtend",
           "pr": {"repo": "rasbt/mlxtend", "number": 1229, "url": "https://github.com/rasbt/mlxtend/pull/1229",
                  "title": "t", "base_sha": "1aee767ef57b84a8191511a08955c583b65de382",
                  "head_sha": "296459ec17120e757a56c7bb08c831469b0e5aa4",
                  "merge_commit": "1af398f8e6305b25d59fba572ec21d51da1fe692"},
           "route": "source-pair", "verdict": "verified", "reason": "1 new test(s) pass, 9 unchanged",
           "files": {"all": [], "package_py": [], "compiled": [], "other": []},
           "machine_type": {"arch": "x86_64", "os": "Linux"},
           "thread_env": {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS")},
           "python": "3.12.15", "runs_per_side": 3, "runs_per_side_planned": 3,
           "per_run": [{"side": s, "run": i, "exit": 0, "seconds": 7.0, "passed": 9, "failed": 0, "error": 0,
                        "skipped": 0, "collection_errors": 0, "pytest_summary": "9 passed"}
                       for i in (1, 2, 3) for s in ("old", "new")],
           "duration_s": {"total_wall": 50.6}, "network": "allowed", "posted_upstream": False,
           "logs": "mlxtend-1229/", "tested_at_ist": "2026-10-10 06:40 IST"}
    rec.update(kw)
    return rec


def test_fix5_pr_run_record_validates_and_bad_one_does_not():
    from ops.schema_check import validate
    assert validate(_pr_record(), SCHEMA) == []
    assert any("verdict" in e for e in validate(_pr_record(verdict="maybe"), SCHEMA))
    bad = _pr_record(); del bad["per_run"]
    assert validate(bad, SCHEMA) == ["$: missing required field 'per_run'"]


def test_fix5_existing_observation_record_still_valid():
    from ops.schema_check import validate
    obs = _json.loads((DAY1 / "observation-golden-clean-sklearn.json").read_text())
    assert "record_kind" not in obs and validate(obs, SCHEMA) == []
    broken = dict(obs); del broken["gates"]
    assert "$: missing required field 'gates'" in validate(broken, SCHEMA)
    assert any("runs_per_side" in e for e in validate(dict(obs, runs_per_side=0), SCHEMA))  # still >= 1 for observations


def test_fix5_stdlib_validator_agrees_with_jsonschema():
    import pytest
    jsonschema = pytest.importorskip("jsonschema")
    from ops.schema_check import validate
    v = jsonschema.Draft202012Validator(SCHEMA)
    obs = _json.loads((DAY1 / "observation-golden-clean-sklearn.json").read_text())
    for rec in (_pr_record(), _pr_record(verdict="x"), _pr_record(runs_per_side=0), obs, dict(obs, accepted="no")):
        assert (not list(v.iter_errors(rec))) == (not validate(rec, SCHEMA))


def test_fix4_report_shows_merge_commit(tmp_path):
    from ops.daily_run import write_report
    rec = _pr_record(author="a", updated_at_ist="x", ci_state="none", ci_detail="-",
                     sides={"merge_parents": ["1aee767ef57b84a8191511a08955c583b65de382",
                                              "296459ec17120e757a56c7bb08c831469b0e5aa4"]},
                     tested={"main": "master @ 1aee767ef57b", "pr": "GitHub test merge commit 1af398f8e630"})
    meta = {"date": "2026-10-10", "started_ist": "s", "finished_ist": "f", "wall_min": 1, "runs": 3, "machine": "m",
            "api_calls": 0, "auth": "none"}
    md = write_report(tmp_path, meta, [rec], {}, []).read_text()
    assert "Merge commit tested: `1af398f8e6305b25d59fba572ec21d51da1fe692`" in md
    assert "APPROVE" in md


# fix 6: superseded attempts kept, selection frozen, dropped PRs listed
def test_fix6_supersede_freeze_and_rerun_section(tmp_path):
    from ops.daily_run import attempt_history, frozen_selection, supersede_previous, write_report
    rdir = tmp_path / "2026-10-10"
    for n, sel in ((2, "selection-attempt-2.json"), (4, "selection-attempt-4.json")):
        d = rdir / "superseded" / f"attempt-{n}"; d.mkdir(parents=True)
        (d / "selection.json").write_text((DAY1 / sel).read_text())
        (d / "NOTE.md").write_text(f"# Attempt {n}\n")
    (rdir / "pandas-70520").mkdir(); (rdir / "records.jsonl").write_text("")
    (rdir / "console.log").write_text("live")
    moved = supersede_previous(rdir, "bug x")
    assert moved.name == "attempt-5" and (moved / "pandas-70520").is_dir() and (rdir / "console.log").exists()
    assert "bug x" in (moved / "NOTE.md").read_text()
    frozen = frozen_selection(rdir)
    assert set(frozen["pandas-dev/pandas"]) == {70812, 70977, 70976, 70520, 70915, 70989}
    assert frozen["pandas-dev/pandas"][70812]["first_attempt"] == "attempt-2"
    meta = {"date": "2026-10-10", "started_ist": "s", "finished_ist": "f", "wall_min": 1, "runs": 3, "machine": "m",
            "api_calls": 0, "auth": "none"}
    md = write_report(rdir, meta, [], {}, [], history=attempt_history(rdir)).read_text()
    assert "## Re-runs" in md
    for n in (70812, 70977, 70976):
        assert f"pandas-dev/pandas#{n}: selected in attempt-2, dropped in attempt-4" in md


# fix 7: thread env, 0 runs on a failed build, unexplained exit codes
def test_fix7_six_thread_vars_pinned(tmp_path):
    from guardrails.isolation import UNTRUSTED_THREAD_ENV
    from ops.daily_run import THREAD_ENV, base_env
    assert set(THREAD_ENV) == {"OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                               "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"}
    assert all(base_env(tmp_path)[k] == "1" for k in THREAD_ENV) and UNTRUSTED_THREAD_ENV == THREAD_ENV


def test_fix7_failed_build_record_says_zero_runs():
    from types import SimpleNamespace

    from ops.daily_run import new_record
    old = _json.loads((DAY1 / "numpy-32910-attempt4-record.json").read_text())
    assert old["runs_per_side"] == 3 and "per_run" not in old           # the day-1 bug
    item = {k: old[k] for k in ("pr", "title", "url", "author", "head_sha", "base_sha", "base_ref", "updated_at_utc",
                                "updated_at_ist", "ci_state", "ci_detail", "files")}
    a = SimpleNamespace(runs=3, workers="4", test_timeout=120, run_timeout=900, build_timeout=1800, python="3.12",
                        python_full="3.12.15")
    rec = new_record("numpy/numpy", {"dist": "numpy", "pkg": "numpy", "nightly": True}, item, a,
                     {"arch": "x86_64", "os": "Linux"}, "2026-10-10")
    assert rec["runs_per_side"] == 0 and rec["runs_per_side_planned"] == 3 and rec["per_run"] == []
    assert rec["route"] == "source-build"


def test_fix7_pandera_identical_errors_explained_and_stated():
    cmp, (v, reason, _) = _verdict("pandera-2552")
    assert v == "verified"
    assert "fail to load on both sides (tests.pandas.test_dtypes)" in reason   # unrelated to the changed files
    assert cmp["load_failed_both"] == ["tests.pandas.test_dtypes"] and "unchanged" in reason


def test_fix7_unexplained_exit_is_not_verified():
    from ops.daily_run import compare_sides, exit_check, verdict_for
    same = {"m::a": ("passed", "")}
    res = {"main": [same] * 3, "pr": [same] * 3}
    cmp = compare_sides(res)
    per_run = [{"side": s, "run": i, "exit": (2 if (s, i) == ("new", 2) else 0)} for i in (1, 2, 3) for s in ("old", "new")]
    ex = exit_check(per_run, res, cmp)
    assert not ex["explained"]
    assert verdict_for(cmp, None, ex)[0] == "could_not_verify"
    per_run = [{"side": s, "run": i, "exit": (1 if s == "new" else 0)} for i in (1, 2, 3) for s in ("old", "new")]
    assert verdict_for(cmp, None, exit_check(per_run, res, cmp))[0] == "could_not_verify"   # exit 1, nothing failed


def test_fix7_map_tests_walks_up_for_compiled_sources(tmp_path):
    from ops.daily_run import map_tests
    t = tmp_path / "numpy" / "_core" / "tests" / "test_item_selection.py"
    t.parent.mkdir(parents=True); t.write_text("")
    files = {"package_py": [], "compiled": ["numpy/_core/src/multiarray/item_selection.c"]}
    assert map_tests(files, "numpy", tmp_path, {}) == ["numpy/_core/tests/test_item_selection.py"]


def test_verification_scoring_ignores_entries_not_rechecked(tmp_path):
    from ops.daily_run import read_verification
    f = tmp_path / "v.jsonl"
    f.write_text("\n".join(_json.dumps(x) for x in (
        {"repo": "rasbt/mlxtend", "pr": 1229, "status": "mismatch", "checker_verdict": "needs_attention"},
        {"repo": "numpy/numpy", "pr": 32910, "status": "unverified", "checker_verdict": "could_not_verify"},
        {"repo": "pandas-dev/pandas", "pr": 70915, "status": "unverified", "checker_verdict": None})))
    assert set(read_verification(f)) == {("rasbt/mlxtend", 1229)}


def test_unchanged_dependency_skips_reported_not_scored(tmp_path):
    from ops.daily_run import unchanged_dependency_skips
    (tmp_path / "junit-pr-1.xml").write_text(
        '<testsuite><testcase classname="m" name="a"><skipped type="pytest.skip" message="Could not import \'torch\'"/>'
        '</testcase><testcase classname="m" name="b"/></testsuite>')
    assert unchanged_dependency_skips(tmp_path, {}) == {"torch": 1}


# ---------------------------------------------------------------- chosen-PRs file: several PRs, plain `- Test:` lines, *_test.py names
CHOSEN_FIXTURE = _Path(__file__).parent / "fixtures" / "chosen" / "day.md"
PANDAS_MISSING = "ModuleNotFoundError: No module named 'pandas'"


def _sides(main, pr):
    return {"main": [main] * 3, "pr": [pr] * 3}


def _per_run(main_exit, pr_exit):
    return [{"side": side, "run": i, "exit": main_exit if side == "old" else pr_exit}
            for i in (1, 2, 3) for side in ("old", "new")]


def test_parse_chosen_fixture_keeps_old_format_and_subsections():
    chosen = dr.parse_chosen(CHOSEN_FIXTURE)
    assert "expected" not in str(chosen).lower()
    old = chosen["acme/widget"][0]
    assert old["pr"] == 12 and old["head_sha"].startswith("0123")
    assert old["test_cmd"].startswith("pytest tests/test_a.py")
    assert dr.chosen_test_targets(old) == ["tests/test_a.py", "tests/test_b.py"]
    nw = chosen["narwhals-dev/narwhals"][0]
    assert nw["pr"] == 4062 and nw["head_sha"] == "a" * 40
    assert nw["test_cmd"] == "pytest tests/expr_and_series/division_by_zero_test.py"
    assert dr.chosen_test_targets(nw) == ["tests/expr_and_series/division_by_zero_test.py"]
    assert nw["install"] == 'pip install -e ".[dev]"'
    nxs = {x["pr"]: x for x in chosen["networkx/networkx"]}
    assert set(nxs) == {8946, 8862}
    assert nxs[8946]["head_sha"] == "56e4499e8f61da4180e2451e8140acf459cf95cc"
    assert nxs[8862]["head_sha"] == "636941793808cba5f84239470afcac2cf336b3eb"
    assert nxs[8946]["install"] == nxs[8862]["install"] == 'pip install -e ".[test]" pytest'
    exp = dr.read_expectations(CHOSEN_FIXTURE)
    assert exp[("acme/widget", 12)] == "needs_attention"
    assert exp[("narwhals-dev/narwhals", 4062)] == "verified"
    assert exp[("networkx/networkx", 8946)] == "verified"
    assert ("networkx/networkx", 8862) not in exp   # non-standard line must not borrow the primary verdict


def test_subsection_install_overrides_the_preamble(tmp_path):
    p = tmp_path / "c.md"
    p.write_text("""## 1. demo
- **Repo:** https://github.com/acme/widget
- Install: `pip install -e .`
- Test: `pytest tests/test_shared.py`
### Primary PR: #1, "a"
  - Head SHA: `1111111111111111111111111111111111111111`
### Secondary PR: #2, "b"
  - Head SHA: `2222222222222222222222222222222222222222`
  - Install: `pip install -e ".[x]"`
- Test (subset, fast): `pytest tests/test_own.py`
""")
    rows = {x["pr"]: x for x in dr.parse_chosen(p)["acme/widget"]}
    assert rows[1]["head_sha"].startswith("1111") and rows[1]["install"] == "pip install -e ."
    assert rows[1]["test_cmd"] == "pytest tests/test_shared.py"
    assert rows[2]["install"] == 'pip install -e ".[x]"'
    assert rows[2]["test_cmd"] == "pytest tests/test_own.py"
    assert dr.read_expectations(p) == {}


def test_map_repo_tests_finds_suffix_test_files(tmp_path):
    for rel in ("tests/expr_and_series/division_by_zero_test.py", "tests/test_graph.py", "tests/graph_test.py",
                "a/test_item.py", "b/test_item.py", "c/item_test.py", "pkg/division_by_zero.py", "pkg/graph.py",
                "pkg/item.py"):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("")
    touched = dr.map_repo_tests({"all": ["tests/expr_and_series/division_by_zero_test.py"], "package_py": []}, tmp_path)
    assert touched == ["tests/expr_and_series/division_by_zero_test.py"]
    by_stem = dr.map_repo_tests({"all": ["pkg/division_by_zero.py"], "package_py": ["pkg/division_by_zero.py"]}, tmp_path)
    assert by_stem == ["tests/expr_and_series/division_by_zero_test.py"]
    prefix = dr.map_repo_tests({"all": ["tests/test_graph.py"], "package_py": []}, tmp_path)
    assert prefix == ["tests/test_graph.py"]
    both = dr.map_repo_tests({"all": ["pkg/graph.py"], "package_py": ["pkg/graph.py"]}, tmp_path)
    assert both == ["tests/test_graph.py", "tests/graph_test.py"]
    capped = dr.map_repo_tests({"all": ["pkg/item.py"], "package_py": ["pkg/item.py"]}, tmp_path)
    assert capped == ["a/test_item.py", "b/test_item.py"]   # two test_*.py hits fill the per-file cap


def test_new_import_failures_are_blocked_not_breaks():
    old, new1, new2 = ("m::test_old[pandas]", "m::test_new[pandas-0]", "m::test_new[pandas-1]")
    ok = "m::test_ok"
    main = {old: ("failed", PANDAS_MISSING), ok: ("passed", "")}
    pr = {old: ("failed", PANDAS_MISSING), ok: ("passed", ""), new1: ("failed", PANDAS_MISSING),
          new2: ("error", "requires pyarrow")}
    res = _sides(main, pr)
    cmp = dr.compare_sides(res)
    assert cmp["new_tests_failing"] == []
    assert {d["test"]: d["module"] for d in cmp["skipped_missing_dependency"]} == {new1: "pandas", new2: "pyarrow"}
    assert cmp["preexisting_failures"] == [old]
    v, reason, _ = dr.verdict_for(cmp, None, dr.exit_check(_per_run(1, 1), res, cmp))
    assert v == "could_not_verify"
    assert "not installed" in reason and "pandas" in reason and "pyarrow" in reason
    assert "new test(s) fail" not in reason and "not explained" not in reason


def test_real_new_failure_and_import_regression_still_need_attention():
    bug, reg = "m::test_bug", "m::test_reg"
    main = {reg: ("passed", ""), "m::test_ok": ("passed", "")}
    pr = {reg: ("failed", PANDAS_MISSING), "m::test_ok": ("passed", ""), bug: ("failed", "AssertionError: expected 1")}
    res = _sides(main, pr)
    cmp = dr.compare_sides(res)
    assert cmp["regressions"] == [reg] and cmp["new_tests_failing"] == [bug]
    assert cmp["skipped_missing_dependency"] == []
    v, reason, _ = dr.verdict_for(cmp, None, dr.exit_check(_per_run(0, 1), res, cmp))
    assert v == "needs_attention" and "new test(s) fail" in reason and "pass on main but fail" in reason


def test_confirm_missing_checks_the_environment(monkeypatch, tmp_path):
    from types import SimpleNamespace
    new = "m::test_new"
    blocked = dr.compare_sides(_sides({}, {new: ("failed", PANDAS_MISSING)}))
    monkeypatch.setattr(dr, "in_side", lambda *a, **k: SimpleNamespace(returncode=0))
    dr.confirm_missing(blocked, tmp_path)
    assert [d["test"] for d in blocked["skipped_missing_dependency"]] == [new]
    assert blocked["new_tests_failing"] == []
    restored = dr.compare_sides(_sides({}, {new: ("failed", PANDAS_MISSING)}))
    monkeypatch.setattr(dr, "in_side", lambda *a, **k: SimpleNamespace(returncode=1))
    dr.confirm_missing(restored, tmp_path)
    assert restored["skipped_missing_dependency"] == [] and restored["new_tests_failing"] == [new]
    assert restored["messages"][new] == PANDAS_MISSING
    skipped = dr.compare_sides(_sides({"m::t": ("passed", "")}, {"m::t": ("skipped", "pytest.skip: requires pyarrow")}))
    dr.confirm_missing(skipped, tmp_path)
    assert skipped["new_tests_failing"] == [] and skipped["skipped_missing_dependency"] == []
    assert any("pyarrow" in x and "installed" in x for x in skipped["other_changes"])


def _junit(cases):
    parts = []
    for cls, name, kind, message in cases:
        if kind == "passed":
            parts.append(f'<testcase classname="{cls}" name="{name}"/>')
        else:
            parts.append(f'<testcase classname="{cls}" name="{name}"><failure message="{message}"/></testcase>')
    return "<testsuite>" + "".join(parts) + "</testsuite>"


def test_rejudge_keeps_unconfirmed_import_failures_as_breaks(tmp_path):
    prdir = tmp_path / "pr"
    prdir.mkdir()
    (prdir / "junit-main-1.xml").write_text(_junit([("m", "test_ok", "passed", "")]))
    (prdir / "junit-pr-1.xml").write_text(_junit([("m", "test_ok", "passed", ""),
                                                  ("m", "test_new", "failed", PANDAS_MISSING)]))
    base = {"runs_per_side": 1, "per_run": [{"side": "old", "run": 1, "exit": 0}, {"side": "new", "run": 1, "exit": 1}],
            "files": {"all": ["pkg/a.py"], "package_py": ["pkg/a.py"], "compiled": []}}
    fresh = dr.rejudge(base | {"comparison": {"skipped_missing_dependency": []}, "verdict": "needs_attention",
                               "reason": "1 new test(s) fail on the PR"}, prdir)
    assert fresh["comparison"]["new_tests_failing"] == ["m::test_new"]
    assert fresh["comparison"]["skipped_missing_dependency"] == []
    assert fresh["verdict"] == "needs_attention"
    kept = dr.rejudge(base | {"comparison": {"skipped_missing_dependency": [
        {"test": "m::test_new", "module": "pandas", "main": "absent"}]}, "verdict": "could_not_verify",
        "reason": "not fully verified: missing pandas"}, prdir)
    assert kept["comparison"]["new_tests_failing"] == []
    assert [d["test"] for d in kept["comparison"]["skipped_missing_dependency"]] == ["m::test_new"]
    assert kept["verdict"] == "could_not_verify" and "not installed" in kept["reason"]


# ---------------------------------------------------------------- flaky tests are listed, and are not a regression (numpy #32992)
DOC_ONLY = {"all": ["doc/source/reference/routines.io.rst"], "package_py": [], "compiled": [],
            "other": ["doc/source/reference/routines.io.rst"]}
NPZ = "numpy/lib/tests/test_io.py::test_npz_docs"


def _flaky_sides(main_runs, pr_runs):
    return dr.compare_sides({"main": main_runs, "pr": pr_runs})


def test_numpy_32992_docs_only_flaky_test_is_could_not_verify():
    """A documentation-only pull request with one test that passes and fails across the 3 runs (numpy #32992)."""
    from poc import coverage_gate
    passed = {NPZ: ("passed", "")}
    failed = {NPZ: ("failed", "intermittent")}
    cmp = _flaky_sides([passed] * 3, [passed, failed, passed])
    assert cmp["flaky"] == [NPZ] and cmp["regressions"] == [] and cmp["new_tests_failing"] == []
    v, reason, labels = dr.verdict_for(cmp, None, None, DOC_ONLY)
    assert v == "could_not_verify"
    assert NPZ in reason and "flaky" in reason
    assert "flaky" in labels
    gated = coverage_gate.apply({"verdict": v, "reason": reason, "files": DOC_ONLY, "comparison": cmp})
    assert gated["verdict"] == "could_not_verify"
    # The same test disagreeing with itself on main is also flaky, not a regression.
    cmp_main = _flaky_sides([passed, failed, passed], [passed] * 3)
    assert cmp_main["flaky"] == [NPZ]
    v_main, reason_main, _ = dr.verdict_for(cmp_main, None, None, DOC_ONLY)
    assert v_main == "could_not_verify" and NPZ in reason_main


def test_flaky_test_does_not_hide_a_real_regression():
    reg = "numpy/lib/tests/test_io.py::test_real"
    main = {NPZ: ("passed", ""), reg: ("passed", "")}
    pr = [{NPZ: ("passed", ""), reg: ("failed", "boom")},
          {NPZ: ("failed", "intermittent"), reg: ("failed", "boom")},
          {NPZ: ("passed", ""), reg: ("failed", "boom")}]
    cmp = _flaky_sides([main] * 3, pr)
    assert cmp["regressions"] == [reg] and cmp["flaky"] == [NPZ]
    v, reason, _ = dr.verdict_for(cmp, None, None, DOC_ONLY)
    assert v == "needs_attention" and "pass on main but fail on the PR" in reason and NPZ in reason


def test_report_lists_a_flaky_test_and_the_header_names_the_commit(tmp_path):
    from ops.daily_run import write_report
    sha = "ab" * 20
    rec = _pr_record(author="a", updated_at_ist="x", ci_state="none", ci_detail="-", poc_commit=sha,
                     verdict="could_not_verify",
                     reason=f"could not verify: 1 flaky test(s): {NPZ}",
                     comparison={"flaky": [NPZ], "regressions": [], "new_tests_failing": [], "removed_tests": [],
                                 "other_changes": []},
                     files=DOC_ONLY)
    meta = {"date": "2026-10-13", "started_ist": "s", "finished_ist": "f", "wall_min": 1, "runs": 3, "machine": "m",
            "api_calls": 0, "auth": "none", "poc_commit": sha}
    md = write_report(tmp_path, meta, [rec], {}, []).read_text()
    header = md.split("##", 1)[0]
    assert f"Proof-of-Change commit: `{sha}`" in header
    assert NPZ in md and "**could_not_verify**" in md


def test_record_check_fails_a_pr_run_without_poc_commit():
    from ops.schema_check import validate
    bare = _pr_record()
    assert validate(bare, SCHEMA) == []                       # schema rev 8 leaves the field optional
    errs = dr.check_record(bare)
    assert any("missing poc_commit" in e for e in errs)
    bad = _pr_record(poc_commit="not-a-commit")
    assert any("poc_commit" in e for e in validate(bad, SCHEMA))
    assert any("40-character" in e for e in dr.check_record(bad))
    sha = "cd" * 20
    assert dr.check_record(_pr_record(poc_commit=sha)) == []
    obs = _json.loads((DAY1 / "observation-golden-clean-sklearn.json").read_text())
    assert dr.check_record(obs) == []                         # an observation record does not carry poc_commit


def test_new_record_stores_the_commit_the_run_used():
    from types import SimpleNamespace
    sha = "ef" * 20
    item = {"pr": 32992, "title": "DOC: clarify NpzFile", "url": "https://github.com/numpy/numpy/pull/32992",
            "author": "a", "head_sha": "a" * 40, "base_sha": "b" * 40, "base_ref": "main",
            "updated_at_utc": "2026-10-12T20:03:29Z", "updated_at_ist": "2026-10-13 01:33 IST",
            "ci_state": "none", "ci_detail": "-", "files": DOC_ONLY}
    a = SimpleNamespace(runs=3, workers="4", test_timeout=120, run_timeout=900, build_timeout=1800, python="3.12",
                        python_full="3.12.15", poc_commit=sha, baseline="full")
    rec = dr.new_record("numpy/numpy", {"dist": "numpy", "pkg": "numpy", "nightly": True}, item, a,
                        {"arch": "x86_64", "os": "Linux"}, "2026-10-13")
    assert rec["poc_commit"] == sha
    missing = dr.new_record("numpy/numpy", {"dist": "numpy", "pkg": "numpy", "nightly": True}, item,
                            SimpleNamespace(runs=3, workers="4", test_timeout=120, run_timeout=900, build_timeout=1800,
                                            python="3.12"),
                            {"arch": "x86_64", "os": "Linux"}, "2026-10-13")
    assert "poc_commit" not in missing


def _git(repo, *args):
    cp = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if cp.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {cp.stderr}")
    return cp.stdout.strip()


def _origin_and_clone(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-b", "main")
    _git(origin, "config", "user.email", "proof-of-change@users.noreply.github.com")
    _git(origin, "config", "user.name", "Proof-of-Change")
    (origin / "README").write_text("one\n")
    _git(origin, "add", "README")
    _git(origin, "commit", "-m", "one")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", str(origin), str(clone)], check=True, capture_output=True, text=True)
    _git(clone, "config", "user.email", "proof-of-change@users.noreply.github.com")
    _git(clone, "config", "user.name", "Proof-of-Change")
    return origin, clone


def test_daily_run_fast_forwards_to_origin_main(tmp_path):
    origin, clone = _origin_and_clone(tmp_path)
    (origin / "README").write_text("two\n")
    _git(origin, "add", "README")
    _git(origin, "commit", "-m", "two")
    _git(clone, "checkout", "-b", "feature")
    sha = dr.sync_to_origin_main(clone)
    assert sha == _git(origin, "rev-parse", "HEAD")
    assert _git(clone, "rev-parse", "HEAD") == sha
    assert _git(clone, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert dr.sync_to_origin_main(clone) == sha                         # already there: still that commit


def test_daily_run_stops_when_it_cannot_fast_forward(tmp_path):
    origin, clone = _origin_and_clone(tmp_path)
    (clone / "README").write_text("dirty\n")
    with pytest.raises(SystemExit, match="uncommitted changes"):
        dr.sync_to_origin_main(clone)
    _git(clone, "checkout", "--", "README")
    (clone / "local-only").write_text("x\n")
    _git(clone, "add", "local-only")
    _git(clone, "commit", "-m", "local only")
    (origin / "remote-only").write_text("y\n")
    _git(origin, "add", "remote-only")
    _git(origin, "commit", "-m", "remote only")
    with pytest.raises(SystemExit, match="diverged"):
        dr.sync_to_origin_main(clone)
    _git(clone, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    with pytest.raises(SystemExit, match="fetching origin main failed"):
        dr.sync_to_origin_main(clone)
