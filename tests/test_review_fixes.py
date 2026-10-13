"""Review fixes for probes, behaviour claims, test mapping and the run record.

Named cases: networkx #8862, skrub #2319, numpy #32992, narwhals #4062, mlxtend #1247, pandas #69808.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from guardrails.schema import validate_record
from ops.daily_run import (
    PIP_OPTIONAL,
    THREAD_ENV,
    attribute_backend_errors,
    change_is_docstring_only,
    combine_run_meta,
    compare_sides,
    how_to_fix,
    installable_missing,
    map_repo_tests,
    mark_holds_by_construction,
    new_record,
    recheck_heads,
    recorded_test_extras,
    save_invocation_meta,
    targets_for_sides,
    verdict_for,
    write_report,
    write_schema_check_log,
)
from ops.daily_run import tests_verdict as verdict_from_tests
from poc import behaviour_claims, coverage_gate, diff_probes, probe_adequacy, probes

ZDIV = "E   ZeroDivisionError: integer division or modulo by zero"
MEM = "7.0 GB memory required, but 5.6 GB available"
LARGE = "numpy/lib/tests/test_io.py::test_large_zip"
HEAD = "a" * 40
OTHER = "b" * 40


def _tri(main, pr):
    return {"main": [main] * 3, "pr": [pr] * 3}


def _touch(root: Path, rel: str, text: str = "") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _base_record(**kw):
    rec = {
        "schema_version": "1", "record_kind": "pr_run",
        "id": "pr-narwhals-dev-narwhals-4062-aaaaaaaaaaaa-2026-10-13",
        "date_ist": "2026-10-13 09:00 IST", "run_date": "2026-10-13", "who": "ops/daily_run.py",
        "repo": "narwhals-dev/narwhals",
        "pr": {"repo": "narwhals-dev/narwhals", "number": 4062,
               "url": "https://github.com/narwhals-dev/narwhals/pull/4062", "title": "t",
               "head_sha": HEAD, "base_sha": OTHER,
               "base_sha_label": "pull request base (not necessarily the main side that was tested)",
               "tested_main_sha": "c" * 40,
               "tested_main_sha_label": "main side that was tested"},
        "route": "source-pair", "verdict": "could_not_verify", "reason": "not a PR finding",
        "files": {"all": ["narwhals/expr.py"], "package_py": ["narwhals/expr.py"], "compiled": [], "other": []},
        "machine_type": {"arch": "x86_64", "os": "Linux"},
        "thread_env": {k: "1" for k in THREAD_ENV} | {"PYTHONHASHSEED": "0"},
        "python": "3.12.1", "runs_per_side": 3, "runs_per_side_planned": 3, "per_run": [],
        "duration_s": {"total_wall": 10}, "network": "allowed", "posted_upstream": False,
        "logs": "narwhals-4062/", "tested_at_ist": "2026-10-13 09:00 IST",
        "author": "a", "updated_at_ist": "2026-10-13 08:00 IST", "ci_state": "none", "ci_detail": "-",
        "current_head_sha": HEAD, "tested_invocation": 1,
        "behaviour_claims": [
            {"source": "changelog", "quote": "passed through unchanged", "pattern": "passed through"},
            {"source": "docstring", "quote": "left unchanged", "pattern": "left unchanged",
             "status": "holds by construction"},
        ],
        "probes": {"status": "uninformative", "items": [{
            "id": "diff-api", "source": "diff", "target": "narwhals-dev/narwhals#4062", "claims": [],
            "runs_per_side": 3, "observations": [], "status": "uninformative",
            "uninformative_reason": "uninformative: every input raised AttributeError on both sides",
        }]},
        "head_at_report_sha": OTHER, "head_moved_since_test": True, "docstring_only": False,
    }
    rec.update(kw)
    return rec


def _report_record(**kw):
    rec = _base_record()
    rec.update(kw)
    return rec


# ---------------------------------------------------------------- networkx #8862: sibling test file first
def test_networkx_8862_sibling_test_wins_over_alphabetical_globs(tmp_path):
    src = "networkx/algorithms/connectivity/connectivity.py"
    sibling = "networkx/algorithms/connectivity/tests/test_connectivity.py"
    for rel in (src, sibling,
                "networkx/algorithms/approximation/tests/test_connectivity.py",
                "networkx/algorithms/assortativity/tests/test_connectivity.py"):
        _touch(tmp_path, rel)
    files = {"all": [src], "package_py": [src], "compiled": [], "other": []}
    mapped = map_repo_tests(files, tmp_path)
    assert mapped[0] == sibling


# ---------------------------------------------------------------- mlxtend #1247: additive tests still have a baseline
def test_mlxtend_1247_additive_pr_runs_nearest_existing_tests(tmp_path):
    main, pr = tmp_path / "main", tmp_path / "pr"
    old = "mlxtend/preprocessing/tests/test_old.py"
    new = "mlxtend/preprocessing/tests/test_new_feature.py"
    src = "mlxtend/preprocessing/new_feature.py"
    _touch(main, old)
    _touch(pr, old)
    _touch(pr, new)
    _touch(pr, src, "def f():\n    return 1\n")
    files = {"all": [src, new], "package_py": [src], "compiled": [], "other": []}
    got = targets_for_sides([new], files, main, pr)
    assert got["main"] == ["mlxtend/preprocessing/tests"]
    assert got["pr"][0] == "mlxtend/preprocessing/tests"
    assert new in got["pr"]


# ---------------------------------------------------------------- skrub #2319: claim phrases in the body, changelog and docstring
SKRUB_DIFF = '''diff --git a/CHANGES.rst b/CHANGES.rst
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -1 +1,2 @@
 notes
+Missing values are passed through unchanged.
diff --git a/skrub/_joiner.py b/skrub/_joiner.py
--- a/skrub/_joiner.py
+++ b/skrub/_joiner.py
@@ -1,2 +1,2 @@
 def join(x):
-    """old text"""
+    """The no-missing path is untouched."""
     return x
'''


def test_skrub_2319_phrases_in_body_changelog_and_docstring_block_verified():
    body = "Missing values are passed through unchanged. The no-missing path is left unchanged."
    found = behaviour_claims.find("Add a joiner", body)
    patterns = {c["pattern"] for c in found}
    assert "passed through" in patterns and "left unchanged" in patterns
    from_diff = behaviour_claims.find("Add a joiner", "No claim in the description.", SKRUB_DIFF)
    sources = {c["source"] for c in from_diff}
    assert sources == {"changelog", "docstring"}
    same = {"t::ok": ("passed", "")}
    cmp = compare_sides(_tri(same, same))
    v, reason, _ = verdict_for(cmp, None, None, {"all": ["skrub/_joiner.py"], "package_py": ["skrub/_joiner.py"],
                                                 "compiled": [], "other": []}, claims=found)
    assert v == "could_not_verify"
    assert "unverified behaviour claim" in reason


# ---------------------------------------------------------------- numpy #32992: a resource skip is the machine
def test_numpy_32992_resource_skip_is_environment_not_a_finding():
    main = [{LARGE: ("passed", "")}, {LARGE: ("skipped", MEM)}, {LARGE: ("passed", "")}]
    pr = [{LARGE: ("skipped", MEM)}, {LARGE: ("passed", "")}, {LARGE: ("skipped", MEM)}]
    cmp = compare_sides({"main": main, "pr": pr})
    assert cmp["flaky"] == [] and cmp["regressions"] == [] and cmp["new_tests_failing"] == []
    assert cmp["environment"] and cmp["environment"][0]["kind"] == "resource"
    assert "memory required" in cmp["environment"][0]["detail"]
    v, reason, _ = verdict_from_tests(cmp, None)
    assert v != "needs_attention"
    assert "environment" in reason
    # A pass/fail change stays flaky even when the failure text mentions memory.
    flaky = compare_sides({"main": [{LARGE: ("passed", "")}, {LARGE: ("failed", MEM)}, {LARGE: ("passed", "")}],
                           "pr": [{LARGE: ("passed", "")}] * 3})
    assert flaky["flaky"] == [LARGE] and flaky["environment"] == []
    assert verdict_from_tests(flaky, None)[0] == "could_not_verify"


def test_docstring_only_holds_by_construction(tmp_path):
    rel = "numpy/lib/_iotools.py"
    main, pr = tmp_path / "main", tmp_path / "pr"
    _touch(main, rel, 'def load(x):\n    """old docs"""\n    return x\n')
    _touch(pr, rel, 'def load(x):\n    """new docs"""\n    return x\n')
    files = {"all": [rel], "package_py": [rel], "compiled": [], "other": []}
    assert coverage_gate.ast_equal_ignoring_docstrings((main / rel).read_text(), (pr / rel).read_text())
    assert change_is_docstring_only(files, main, pr)
    _touch(pr, rel, 'def load(x):\n    """new docs"""\n    return x + 1\n')
    assert not change_is_docstring_only(files, main, pr)
    same = {"t::ok": ("passed", "")}
    cmp = compare_sides(_tri(same, same))
    claims = [{"source": "PR description", "quote": "The file is left unchanged.", "pattern": "left unchanged"}]
    blocked, _, _ = verdict_for(cmp, None, None, files, claims=claims)
    assert blocked == "could_not_verify"
    v, reason, labels = verdict_for(cmp, None, None, files, claims=claims, docstring_only=True)
    assert v == "verified" and "hold by construction" in reason and "holds_by_construction" in labels
    assert mark_holds_by_construction(claims)[0]["status"] == "holds by construction"
    # A real regression is still needs attention.
    reg = {"t::ok": ("passed", "")}
    bad = {"t::ok": ("failed", "AssertionError: boom")}
    regression = compare_sides(_tri(reg, bad))
    assert verdict_for(regression, None, None, files, docstring_only=True)[0] == "needs_attention"


# ---------------------------------------------------------------- narwhals #4062: same backend error on base is not a PR finding
def test_narwhals_4062_ibis_zero_division_on_base_is_could_not_verify():
    """After ibis is installed, three new tests fail with ZeroDivisionError on `% 0`.

    The same error happens on the base side, so it is the backend. The verdict is could_not_verify.
    """
    assert PIP_OPTIONAL["ibis"] == "ibis-framework"
    assert installable_missing({"skipped_missing_dependency": [
        {"module": "ibis"}, {"module": "ibis.backends"}, {"module": "not_a_wheel"},
    ]}) == ["ibis"]
    old = "tests.expr_and_series.division_by_zero_test::test_mod_pandas"
    new = [f"tests.expr_and_series.division_by_zero_test::test_ibis_{name}"
           for name in ("mod", "truediv", "floordiv")]
    main = {old: ("failed", ZDIV), "tests.other::test_ok": ("passed", "")}
    pr = dict(main)
    for t in new:
        pr[t] = ("failed", ZDIV)
    results = _tri(main, pr)
    cmp = compare_sides(results)
    assert old in cmp["preexisting_failures"]
    assert cmp["new_tests_failing"] == sorted(new)
    attribute_backend_errors(cmp, results)
    assert cmp["new_tests_failing"] == []
    assert [d["test"] for d in cmp["backend_same_error"]] == sorted(new)
    v, reason, _ = verdict_from_tests(cmp, None)
    assert v == "could_not_verify"
    assert "not a PR finding" in reason and "ZeroDivisionError" in reason


def test_backend_error_seen_only_via_base_rerun_is_could_not_verify():
    """The new files do not exist on base. Copying them there raises the same ZeroDivisionError."""
    new = [f"tests.expr_and_series.division_by_zero_test::test_ibis_{name}" for name in ("a", "b", "c")]
    main = {"tests.other::test_ok": ("passed", "")}
    pr = dict(main)
    for t in new:
        pr[t] = ("failed", ZDIV)
    results = _tri(main, pr)
    cmp = compare_sides(results)
    attribute_backend_errors(cmp, results, ["ZeroDivisionError"])
    assert cmp["new_tests_failing"] == []
    v, reason, _ = verdict_from_tests(cmp, None)
    assert v == "could_not_verify" and "not a PR finding" in reason


def test_new_assertion_error_not_on_base_stays_needs_attention():
    new = "tests.expr_and_series.division_by_zero_test::test_ibis_new"
    main = {"tests.other::test_ok": ("passed", "")}
    pr = dict(main, **{new: ("failed", "AssertionError: expected 1")})
    results = _tri(main, pr)
    cmp = compare_sides(results)
    attribute_backend_errors(cmp, results, ["ZeroDivisionError"])
    assert cmp["new_tests_failing"] == [new]
    assert verdict_from_tests(cmp, None)[0] == "needs_attention"
    # A test that passed on base and fails on the pull request stays a regression.
    reg = "tests.other::test_ok"
    results = _tri({reg: ("passed", "")}, {reg: ("failed", ZDIV)})
    cmp = compare_sides(results)
    attribute_backend_errors(cmp, results, ["ZeroDivisionError"])
    assert cmp["regressions"] == [reg]
    assert verdict_from_tests(cmp, None)[0] == "needs_attention"


# ---------------------------------------------------------------- uninformative probes do not count (networkx #8862 / mlxtend #1246)
def _attr_item():
    obs = [{"name": f"f.input{i}", "state": "same", "label": "no_difference",
            "main": {"raises": "AttributeError"}, "pr": {"raises": "AttributeError"}} for i in range(3)]
    return {"id": "diff-api", "observations": obs, "claims": [{"id": "c", "text": "same", "covers": ["*"],
                                                               "expect": "same"}],
            "probe_changed_line_coverage": {"status": "measured", "changed_lines_total": 8,
                                            "changed_lines_covered": 2, "adequacy": "adequate",
                                            "note": "ran 2 of 8 changed line(s) on the main side"}}


def test_uninformative_probe_is_not_ran_or_adequate():
    item = probes.classify_item(_attr_item())
    assert item["status"] == "uninformative"
    assert item["probe_changed_line_coverage"]["adequacy"] == "not_adequate"
    applied = probes.apply_status({"status": "ran", "items": [_attr_item()]})
    assert applied["status"] == "uninformative"
    assert not behaviour_claims.probe_covers(applied)
    kept, notes = probe_adequacy.deciding_items(applied["items"])
    assert kept[0]["observations"] == [] and notes
    same = {"t::ok": ("passed", "")}
    v, reason, _ = verdict_for(compare_sides(_tri(same, same)), None, None, None, applied,
                               claims=[{"source": "PR description", "quote": "left unchanged",
                                        "pattern": "left unchanged"}])
    assert v == "could_not_verify" and "unverified behaviour claim" in reason


def test_type_aware_probe_uses_a_graph_and_skips_when_it_cannot(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "m.py").write_text("def node_connectivity(G):\n    return G.number_of_nodes()\n")
    ok = tmp_path / "nx_ok" / "networkx"
    ok.mkdir(parents=True)
    (ok / "__init__.py").write_text(
        "class G:\n"
        "    def __init__(self, n):\n"
        "        self.n = n\n"
        "    def number_of_nodes(self):\n"
        "        return self.n\n"
        "def path_graph(n):\n"
        "    return G(n)\n")
    bad = tmp_path / "nx_bad" / "networkx"
    bad.mkdir(parents=True)
    (bad / "__init__.py").write_text("raise ImportError('no graph library')\n")
    path = diff_probes.write([("pkg.m", "node_connectivity")], tmp_path / "diff-api.py", "networkx/networkx#8862")

    def run(extra):
        env = {"PATH": os.environ["PATH"], "PYTHONPATH": os.pathsep.join([str(tmp_path), str(extra)])}
        out = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, cwd=tmp_path, env=env)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)["observations"]

    hit = run(tmp_path / "nx_ok")
    assert hit["pkg.m.node_connectivity.input0"] == 4
    skipped = run(tmp_path / "nx_bad")
    assert skipped["pkg.m.node_connectivity.input0"] == {"skipped": "no type-aware input"}
    item = {"id": "diff-api", "observations": [{
        "name": "pkg.m.node_connectivity.input0", "state": "same", "label": "no_difference",
        "main": skipped["pkg.m.node_connectivity.input0"], "pr": skipped["pkg.m.node_connectivity.input0"]}]}
    assert probes.classify_item(item)["status"] == "not_run"
    assert probes.apply_status({"status": "ran", "items": [item]})["status"] == "none"


# ---------------------------------------------------------------- records: extras, hash seed, SHAs, resume, how to fix, schema log
def test_recorded_extras_are_the_packages_inside_the_extra(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'narwhals'\n"
        "[project.optional-dependencies]\ndev = ['pandas', 'pyarrow>=1', 'polars']\n")
    assert recorded_test_extras(tmp_path, ["-e", f"{tmp_path}[dev]"]) == ["pandas", "pyarrow", "polars"]


def test_new_record_pins_hash_seed_and_names_the_shas():
    item = {"pr": 69808, "title": "t", "url": "https://github.com/pandas-dev/pandas/pull/69808", "author": "a",
            "head_sha": HEAD, "base_sha": OTHER, "base_ref": "main", "updated_at_utc": "u", "updated_at_ist": "i",
            "ci_state": "none", "ci_detail": "-", "files": {"all": [], "package_py": [], "compiled": [], "other": []},
            "body": "", "diff": ""}
    a = SimpleNamespace(runs=3, workers="4", test_timeout=120, run_timeout=900, build_timeout=1800, python="3.12",
                        baseline="tests", model_provider="none", model_note=None, invocation=2)
    rec = new_record("pandas-dev/pandas", {"dist": "pandas", "pkg": "pandas", "nightly": True}, item, a,
                     {"arch": "x86_64", "os": "Linux"}, "2026-10-13")
    assert set(THREAD_ENV) == {"OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                               "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"}
    assert "PYTHONHASHSEED" not in THREAD_ENV
    assert rec["thread_env"]["PYTHONHASHSEED"] == "0"
    assert rec["current_head_sha"] == HEAD
    assert rec["tested_invocation"] == 2
    assert "pull request base" in rec["pr"]["base_sha_label"]
    assert rec["pr"]["base_sha"] == OTHER


def test_resume_keeps_the_first_start_and_lists_reused_records(tmp_path):
    first = {"invocation": 1, "started_ist": "2026-10-13 09:00 IST", "finished_ist": "2026-10-13 09:20 IST",
             "wall_min": 20.0, "date": "2026-10-13", "runs": 3, "machine": "m", "api_calls": 1, "auth": "none",
             "problems": []}
    save_invocation_meta(tmp_path, first)
    this = {"invocation": 2, "started_ist": "2026-10-13 09:40 IST", "finished_ist": "2026-10-13 09:42 IST",
            "wall_min": 1.6, "date": "2026-10-13", "runs": 3, "machine": "m", "api_calls": 0, "auth": "none",
            "problems": [], "reused": [{"repo": "pandas-dev/pandas", "pr": 69808, "from_invocation": 1,
                                        "tested_at_ist": "2026-10-13 09:10 IST"}]}
    save_invocation_meta(tmp_path, this)
    records = [{"duration_s": {"total_wall": 600}}, {"duration_s": {"total_wall": 1050}}]
    meta = combine_run_meta(tmp_path, this, records)
    assert meta["started_ist"] == "2026-10-13 09:00 IST"
    assert meta["wall_min"] == 27.5 and meta["wall_min_this_invocation"] == 1.6
    assert (tmp_path / "invocations" / "invocation-1" / "run_meta.json").is_file()
    assert json.loads((tmp_path / "invocations" / "invocation-1" / "run_meta.json").read_text())["wall_min"] == 20.0
    rec = _report_record(repo="pandas-dev/pandas")
    rec["pr"] = dict(rec["pr"], repo="pandas-dev/pandas", number=69808,
                     url="https://github.com/pandas-dev/pandas/pull/69808", title="moved", head_sha=HEAD)
    recheck_heads([rec], lambda repo, number: OTHER)
    assert rec["head_moved_since_test"] is True and rec["head_at_report_sha"] == OTHER
    md = write_report(tmp_path, meta, [rec], {}, []).read_text()
    assert "Head moved after the test" in md
    assert "pandas-dev/pandas#69808: reused from invocation 1" in md
    assert "Tested main SHA" in md


def test_how_to_fix_agrees_with_coverage_and_schema_log_counts(tmp_path):
    reason = ("not fully verified: 3 new/changed test(s) skipped or blocked because optional dependency ibis "
              "not installed (20 tests ran)")
    text = how_to_fix({"repo": "narwhals-dev/narwhals", "pr": {"number": 4062}, "reason": reason,
                       "coverage": {"status": "measured", "changed_lines_covered": 20, "changed_lines_total": 21}})
    assert "never ran the changed lines" not in text
    assert "20 of 21" in text
    plain = how_to_fix({"repo": "narwhals-dev/narwhals", "pr": {"number": 4062},
                        "reason": "not fully verified: the check stopped early",
                        "coverage": {"status": "measured", "changed_lines_covered": 20, "changed_lines_total": 21}})
    assert "never ran" not in plain and "20 of 21" in plain
    good, bad = _base_record(), _base_record(schema_errors=["probes.status: bad"])
    path = write_schema_check_log(tmp_path, [good, bad])
    lines = path.read_text().splitlines()
    assert lines[0] == "1/2 valid"
    assert write_schema_check_log(tmp_path, [good, good]).read_text().splitlines()[0] == "2/2 valid"


def test_rev9_fields_validate_and_old_enums_stay_closed():
    assert validate_record(_base_record()) == []
    bad_seed = _base_record()
    bad_seed["thread_env"]["PYTHONHASHSEED"] = "1"
    assert any("PYTHONHASHSEED" in e for e in validate_record(bad_seed))
    bad_status = _base_record()
    bad_status["probes"]["status"] = "nope"
    assert any("probes.status" in e for e in validate_record(bad_status))
    bad_source = _base_record()
    bad_source["behaviour_claims"][0]["source"] = "email"
    assert any("source" in e for e in validate_record(bad_source))
