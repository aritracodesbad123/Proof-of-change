"""Narrow cross-run: new or changed tests that fail on the base and pass on the PR may settle a differs claim.

The two regression fixtures are modelled on dask #12645 and rich #4147. Both pass the cross-run and both stay
not verified. Nothing from those pull requests is run again.
"""
import copy
import json
from pathlib import Path

from evals.checks import derive_verdict
from ops.daily_run import compare_sides, cross_run_test_ids, pr_side_crash, verdict_for
from poc import probes

FX = Path(__file__).resolve().parent / "fixtures" / "narrow_cross_run"
COV = {"status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1, "adequacy": "adequate"}


def _load(name):
    return json.loads((FX / name).read_text())


def _comparison(spec):
    def side(rows):
        one = {k: (v, "assertion failed" if v in ("failed", "error") else "") for k, v in rows.items()}
        return [one] * 3

    return compare_sides({"main": side(spec["tests"]["main"]), "pr": side(spec["tests"]["pr"])})


def _files(spec):
    all_files = list(spec["files"])
    return {"all": all_files, "package_py": list(spec.get("package_py") or []), "compiled": [],
            "other": [f for f in all_files if f not in (spec.get("package_py") or [])]}


def _probes(spec):
    items = []
    for raw in spec["probes"]:
        body = {"id": raw["id"], "target": raw.get("target", "o/r#1"), "about": raw.get("about", "x"),
                "claims": raw["claims"]}
        item = probes.entry(body, {"main": [raw["main"]] * 3, "pr": [raw["pr"]] * 3}, None, [],
                            raw.get("source", "model"), None)
        item["status"] = "ran"
        item["probe_changed_line_coverage"] = dict(COV)
        if raw.get("unable_to_reach"):
            item["unable_to_reach"] = raw["unable_to_reach"]
        items.append(item)
    return {"status": "ran", "items": items}


def _judge(name):
    spec = _load(name)
    files = _files(spec)
    cmp = _comparison(spec)
    pp = _probes(spec)
    return spec, files, cmp, pp, verdict_for(cmp, None, None, files, pp)


def _record(name):
    spec, files, cmp, pp, _v = _judge(name)
    return {"comparison": cmp, "files": files, "probes": pp, "baseline": "full", "product_check": False,
            "coverage": {"status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1},
            "behaviour_claims": [], "docstring_only": False, "repo": spec.get("repo"), "pr": spec.get("pr")}


def test_agreeing_differs_claim_with_a_cross_run_is_verified():
    _spec, _files_d, cmp, _pp, (v, reason, fl) = _judge("agreeing-settled.json")
    assert cross_run_test_ids(cmp, _files_d)
    assert v == "verified"
    assert "cross_run_settled" in fl
    assert "cross-run settled differs claim(s) C1 as proven" in reason
    assert "fail on the base and pass on the PR" in reason
    assert "need attention" not in reason
    assert derive_verdict(_record("agreeing-settled.json"), "full") == "verified"


def test_a_differs_claim_whose_probes_never_ran_is_verified():
    v, reason, fl = _judge("never-ran-settled.json")[4]
    assert v == "verified" and "cross_run_settled" in fl and "C1" in reason
    assert "need attention" not in reason


def test_without_the_cross_run_the_agreeing_claim_still_needs_attention():
    spec = _load("agreeing-settled.json")
    spec["files"] = ["pkg/mod.py"]
    files = _files(spec)
    cmp = _comparison(spec)
    assert cross_run_test_ids(cmp, files) == []
    v, reason, fl = verdict_for(cmp, None, None, files, _probes(spec))
    assert v == "needs_attention"
    assert "does not differ although the claim says it does" in reason
    assert "cross_run_settled" not in fl


def test_dask_12645_passes_the_cross_run_and_stays_not_verified():
    """A claimed no-change result did change. The new cases fail on the base and pass on the PR."""
    spec, files, cmp, _pp, (v, reason, fl) = _judge("dask-12645.json")
    ids = cross_run_test_ids(cmp, files)
    assert any(i.endswith("test_parse_timedelta[.5s]") for i in ids)
    assert any(i.endswith("test_parse_timedelta[.25 seconds]") for i in ids)
    assert v != "verified" and v == "needs_attention"
    assert "cross_run_settled" not in fl
    assert "differs although the claim says it does not" in reason
    assert spec["package_py"] == ["dask/utils.py"]


def test_rich_4147_passes_the_cross_run_and_stays_not_verified():
    """The new regression test fails on the base and passes on the PR. Another behaviour changed with no claim."""
    _spec, files, cmp, _pp, (v, reason, fl) = _judge("rich-4147.json")
    ids = cross_run_test_ids(cmp, files)
    assert any(i.endswith("test_adjacent_tags") for i in ids)
    assert v != "verified" and v == "needs_attention"
    assert "cross_run_settled" not in fl
    assert "no claim covers it" in reason


def test_a_same_claim_that_differed_is_not_verified():
    v, reason, fl = _judge("exclusion-same-claim.json")[4]
    assert v != "verified"
    assert "cross_run_settled" not in fl
    assert "differs although the claim says it does not" in reason


def test_an_unclaimed_difference_is_not_verified():
    v, reason, fl = _judge("exclusion-unclaimed.json")[4]
    assert v != "verified"
    assert "cross_run_settled" not in fl
    assert "no claim covers it" in reason


def test_a_crash_on_the_pr_side_is_not_verified():
    _spec, _files_d, _cmp, pp, (v, _reason, fl) = _judge("exclusion-pr-crash.json")
    assert pr_side_crash(pp)
    assert v != "verified" and "cross_run_settled" not in fl
    # The crash is only in the recorded runs, not a separate unclaimed observation.
    _spec2, files, cmp, pp, _verdict = _judge("agreeing-settled.json")
    assert verdict_for(cmp, None, None, files, pp)[0] == "verified"
    crashed = copy.deepcopy(pp)
    for run in crashed["items"][0]["runs"]["pr"]:
        run[probes.PROBE_ERROR] = {"crash": "non-json output"}
    assert pr_side_crash(crashed)
    v, _reason, fl = verdict_for(cmp, None, None, files, crashed)
    assert v != "verified" and "cross_run_settled" not in fl


def test_tests_that_fail_on_the_pr_are_not_verified():
    _spec, files, cmp, _pp, (v, reason, fl) = _judge("exclusion-tests-fail.json")
    assert cross_run_test_ids(cmp, files)
    assert cmp["regressions"]
    assert v != "verified" and "cross_run_settled" not in fl
    assert "fail on the PR" in reason


def test_a_failure_already_on_both_sides_is_not_verified():
    spec = _load("agreeing-settled.json")
    spec["tests"]["main"]["pkg/tests/test_mod.py::test_pre"] = "failed"
    spec["tests"]["pr"]["pkg/tests/test_mod.py::test_pre"] = "failed"
    files = _files(spec)
    cmp = _comparison(spec)
    assert cmp["preexisting_failures"] and cross_run_test_ids(cmp, files)
    v, _reason, fl = verdict_for(cmp, None, None, files, _probes(spec))
    assert v != "verified" and "cross_run_settled" not in fl


def test_no_new_tests_means_no_cross_run_and_nothing_changes():
    spec, files, cmp, _pp, (v, reason, fl) = _judge("no-new-tests.json")
    assert spec["files"] == ["pkg/mod.py"]
    assert cmp["new_tests_passing"] == 0 and cmp["fixed"]
    assert cross_run_test_ids(cmp, files) == []
    assert v == "needs_attention"
    assert "cross_run_settled" not in fl
    assert "does not differ although the claim says it does" in reason
    bare, bare_files, bare_cmp, _pp2, (v2, reason2, fl2) = _judge("new-tests-not-on-base.json")
    assert bare_cmp["new_tests_passing"] == 1 and not bare_cmp["fixed"]
    assert cross_run_test_ids(bare_cmp, bare_files) == []
    assert v2 == "needs_attention" and "cross_run_settled" not in fl2
    assert "does not differ although the claim says it does" in reason2
    assert bare["files"]


def test_a_differs_claim_whose_probes_did_not_all_agree_is_not_settled():
    v, reason, fl = _judge("probes-not-all-agreed.json")[4]
    assert v == "needs_attention"
    assert "cross_run_settled" not in fl
    assert "does not differ although the claim says it does" in reason


def test_agreeing_inputs_the_probe_could_not_reach_are_still_settled():
    spec = _load("agreeing-settled.json")
    spec["probes"][0]["unable_to_reach"] = "unable to reach the change: the probe never called the new code"
    files = _files(spec)
    cmp = _comparison(spec)
    v, reason, fl = verdict_for(cmp, None, None, files, _probes(spec))
    assert v == "verified" and "cross_run_settled" in fl
    assert "C1" in reason


def test_a_differs_claim_the_probes_already_proved_is_unchanged():
    spec = _load("agreeing-settled.json")
    spec["probes"][0]["pr"] = {"out": 2}
    files = _files(spec)
    cmp = _comparison(spec)
    v, reason, fl = verdict_for(cmp, None, None, files, _probes(spec))
    assert v == "verified" and "cross_run_settled" not in fl
    assert "C1 proven" in reason
