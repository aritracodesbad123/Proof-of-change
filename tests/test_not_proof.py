import json
from pathlib import Path

import pytest

from ops.daily_run import compare_sides, verdict_for
from poc import probes

FL = probes.FindingLabel


def _item(claims, main, pr, pid="model-p1"):
    spec = {"id": pid, "source": "model", "claims": claims}
    runs = {"main": [dict(main) for _ in range(3)], "pr": [dict(pr) for _ in range(3)]}
    item = {"id": pid, "source": "model", "claims": claims, "observations": probes.judge(spec, runs),
            "probe_changed_line_coverage": {"status": "measured", "changed_lines_total": 1,
                                            "changed_lines_covered": 1, "adequacy": "adequate"}}
    return item


def _verified_cmp():
    same = {"t::a": ("passed", "")}
    return compare_sides({"main": [same] * 3, "pr": [same] * 3})


CHANGE = {"id": "C1", "text": "adjacent tags now match separately", "covers": ["C1.*"], "expect": "differs"}
KEEP = {"id": "C2", "text": "Existing behaviour is preserved.", "covers": ["C2.*"], "expect": "same"}
TEST_ADDED = {"id": "C3", "text": "A regression test was added.", "covers": ["C3.*"], "expect": "same"}


def _obs(item, name):
    return next(o for o in item["observations"] if o["name"] == name)


def test_same_claim_on_one_example_is_not_proof():
    it = _item([CHANGE, KEEP], {"C1.out": 1, "C2.single_tag_match_count": 1, "C2.single_tag_matches": ["<a>"]},
               {"C1.out": 2, "C2.single_tag_match_count": 1, "C2.single_tag_matches": ["<a>"]})
    for n in ("C2.single_tag_match_count", "C2.single_tag_matches"):
        assert _obs(it, n)["label"] == FL.NOT_TESTABLE.value and _obs(it, n)["not_proof"]
    assert probes.unproven_claims({"items": [it]}) == ["C2"]
    v, reason, fl = verdict_for(_verified_cmp(), None, None, None, {"status": "ran", "items": [it]})
    assert v == "could_not_verify" and "C2 not proven" in reason and "claim_not_proven" in fl


def test_same_claim_on_several_examples_still_proves():
    it = _item([CHANGE, KEEP], {"C1.out": 1, "C2.plain": 1, "C2.nested": 2, "C2.empty": 0},
               {"C1.out": 2, "C2.plain": 1, "C2.nested": 2, "C2.empty": 0})
    assert {_obs(it, n)["label"] for n in ("C2.plain", "C2.nested", "C2.empty")} == {FL.PROVEN.value}
    assert probes.unproven_claims({"items": [it]}) == []


def test_import_check_proves_no_claim():
    it = _item([CHANGE, TEST_ADDED], {"C1.out": 1, "C3.test_import_success": True},
               {"C1.out": 2, "C3.test_import_success": True})
    o = _obs(it, "C3.test_import_success")
    assert o["label"] == FL.NOT_TESTABLE.value and o["not_proof"] == probes.RUNS_ONLY_NOTE
    assert verdict_for(_verified_cmp(), None, None, None, {"status": "ran", "items": [it]})[0] == "could_not_verify"


def test_import_that_changes_is_not_runs_only():
    claim = {"id": "C1", "text": "the module now imports", "covers": ["C1.*"], "expect": "differs"}
    it = _item([claim], {"C1.import_ok": "ImportError"}, {"C1.import_ok": True})
    assert _obs(it, "C1.import_ok")["label"] == FL.PROVEN.value


def test_flags_are_never_removed():
    it = _item([KEEP], {"C2.single": 1}, {"C2.single": 2})
    assert _obs(it, "C2.single")["label"] == FL.FALSE_CLAIM.value
    assert verdict_for(_verified_cmp(), None, None, None, {"status": "ran", "items": [it]})[0] == "needs_attention"


@pytest.mark.parametrize("name,expect", [("C3.single_tag_match_count", "single_tag"),
                                         ("C3.single_tag_matches", "single_tag"),
                                         ("ipv4_plain_match", "ipv4_plain"), ("ipv4_cidr_match", "ipv4_cidr"),
                                         ("C2.case1.rel", "case1")])
def test_example_of(name, expect):
    assert probes._example_of(name, name.split(".")[0] if name.startswith("C") else None) == expect
