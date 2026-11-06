"""Settler scope and stored-route parity.

A fixed row in a file that is not a default test name, and a shared id, stay fixed and do not settle a
differs claim. The stored rejudge path applies the same evidence filters as a live finalize, on a copy of
the saved comparison. These are synthetic records. They are not historic verification.
"""
import copy

from evals.checks import derive_verdict
from ops import daily_run as dr
from poc import probes

COV = {"status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1, "adequacy": "adequate"}
FILES = {"all": ["pkg/mod.py", "tests/test_mod.py"], "package_py": ["pkg/mod.py"], "compiled": []}
TID = "tests.test_mod::test_kept"


def _evidence(**extra) -> dict:
    base = {"ids": [], "shared_ids": [], "passed_on_base": [], "failed_on_base": [], "not_collected": [],
            "not_executed": [], "collection_failed": [], "discovery_empty": [], "environment_limits": [],
            "reproduced": False}
    base.update(extra)
    return base


def _probe(claims, main, pr):
    body = {"id": "model-p1", "target": "o/r#1", "about": "x", "claims": claims}
    item = probes.entry(body, {"main": [main] * 3, "pr": [pr] * 3}, None, [], "model", None)
    item["status"] = "ran"
    item["probe_changed_line_coverage"] = dict(COV)
    return {"status": "ran", "items": [item]}


def _agreed():
    return _probe([{"id": "C1", "text": "the returned value changes", "covers": ["out"], "expect": "differs"}],
                  {"out": 1}, {"out": 1})


def _unmatched():
    return _probe([{"id": "C1", "text": "the score changes", "covers": ["gone.*"], "expect": "differs"}],
                  {"out": 1}, {"out": 1})


def _record(cmp, probe, files=None) -> dict:
    return {"comparison": cmp, "files": files or FILES, "probes": probe, "baseline": "tests+probes",
            "product_check": False, "behaviour_claims": [], "docstring_only": False, "exit_check": None}


def _live(cmp, probe, files=None):
    filtered = copy.deepcopy(cmp)
    dr.apply_execution_evidence_filters(filtered)
    v, reason, fl = dr.verdict_for(filtered, None, None, files or FILES, probe, baseline="tests+probes")
    v, reason = dr.cap_for_uncollected_file(filtered, v, reason)
    return filtered, v, reason, fl


def test_a_shared_id_in_an_edited_default_file_does_not_settle_an_agreed_claim():
    """The same assertion failure settles only when the id is not a shared execution."""
    row = {TID: ("failed", "AssertionError: assert 1 == 2")}
    passed = {TID: ("passed", "")}
    cmp = dr.compare_sides({"main": [row] * 3, "pr": [passed] * 3})
    cmp["base_new_tests"] = _evidence(shared_ids=["tests/test_mod.py::test_kept"])
    assert TID in cmp["fixed"]
    assert dr.cross_run_test_ids(cmp, FILES) == []
    _filtered, v, reason, fl = _live(cmp, _agreed())
    assert v == "needs_attention" and "cross_run_settled" not in fl
    assert "as proven" not in reason
    assert derive_verdict(_record(cmp, _agreed()), "tests+probes") == v
    bare = copy.deepcopy(cmp)
    bare["base_new_tests"] = _evidence()
    assert dr.cross_run_test_ids(bare, FILES) == [TID]
    _bf, bv, _br, bfl = _live(bare, _agreed())
    assert bv == "verified" and "cross_run_settled" in bfl


def test_an_import_gap_drops_on_the_live_path_and_on_rejudge(tmp_path):
    """A saved base_new_tests stamp does not put an ImportError back into fixed or into a settlement."""
    message = "ModuleNotFoundError: No module named 'pkg.helper_util'"
    failed = {TID: ("failed", message)}
    passed = {TID: ("passed", "")}
    cmp = dr.compare_sides({"main": [failed] * 3, "pr": [passed] * 3})
    cmp["base_new_tests"] = _evidence(ids=["tests/test_mod.py::test_kept"])
    saved_fixed = list(cmp["fixed"])
    assert TID in saved_fixed
    filtered, v, reason, fl = _live(cmp, _unmatched())
    assert TID not in filtered["fixed"]
    assert v == "could_not_verify" and "cross_run_settled" not in fl and "as proven" not in reason
    assert "helper_util" in " ".join(filtered["base_new_tests"]["environment_limits"])
    assert derive_verdict(_record(cmp, _unmatched()), "tests+probes") == v
    assert cmp["fixed"] == saved_fixed

    prdir = tmp_path / "pr"
    prdir.mkdir()
    for side, cases in (("main", failed), ("pr", passed)):
        for i in range(1, 4):
            body = []
            for tid, (outcome, msg) in cases.items():
                cls, name = tid.split("::", 1)
                if outcome == "passed":
                    body.append(f'<testcase classname="{cls}" name="{name}"/>')
                else:
                    body.append(f'<testcase classname="{cls}" name="{name}"><failure message="{msg}"/></testcase>')
            (prdir / f"junit-{side}-{i}.xml").write_text(
                f'<testsuites><testsuite tests="{len(cases)}">{"".join(body)}</testsuite></testsuites>')
    rec = _record(cmp, _unmatched())
    rec["runs_per_side"] = 3
    rec["per_run"] = []
    out = dr.rejudge(rec, prdir)
    assert TID not in out["comparison"]["fixed"]
    assert out["verdict"] == v
    assert "cross-run settled" not in out["reason"]
    assert cmp["fixed"] == saved_fixed
    assert rec["comparison"]["base_new_tests"]["environment_limits"] == []


def test_a_collection_gap_caps_only_a_verified_result():
    passed = {"tests/test_old.py::test_old": ("passed", "")}
    clean = dr.compare_sides({"main": [passed] * 3, "pr": [passed] * 3})
    clean["base_new_tests"] = _evidence(collection_failed=["tests/checks.py"])
    files = {"all": ["pkg/mod.py", "tests/test_old.py", "tests/checks.py"], "package_py": ["pkg/mod.py"],
             "compiled": []}
    _filtered, v, reason, _fl = _live(clean, {"status": "ran", "items": []}, files)
    assert v == "could_not_verify" and "tests/checks.py" in reason
    assert derive_verdict(_record(clean, {"status": "ran", "items": []}, files), "tests+probes") == v

    reg_main = {"tests/test_old.py::test_old": ("passed", "")}
    reg_pr = {"tests/test_old.py::test_old": ("failed", "AssertionError: assert False")}
    reg = dr.compare_sides({"main": [reg_main] * 3, "pr": [reg_pr] * 3})
    reg["base_new_tests"] = _evidence(collection_failed=["tests/checks.py"])
    _rf, rv, _rr, _rfl = _live(reg, {"status": "ran", "items": []}, files)
    assert rv == "needs_attention"
    assert derive_verdict(_record(reg, {"status": "ran", "items": []}, files), "tests+probes") == "needs_attention"


def test_dask_12645_stays_needs_attention():
    from tests.test_narrow_cross_run import _judge
    _spec, files, cmp, _pp, (v, _reason, fl) = _judge("dask-12645.json")
    assert dr.cross_run_test_ids(cmp, files)
    assert v == "needs_attention" and "cross_run_settled" not in fl
