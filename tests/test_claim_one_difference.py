"""A claim that says something changes is met per input when at least one of its checked values differs; the
input's other values that stayed the same are advisory only (poc/probes.py summarize)."""
import copy
import json
from pathlib import Path

from evals.checks import derive_verdict
from ops import daily_run as dr
from poc import probes
from poc.verdict import FindingLabel

FX = Path(__file__).resolve().parent / "fixtures/claim_one_difference"
P, NH = FindingLabel.PROVEN.value, FindingLabel.NEEDS_HUMAN.value


def _o(name, state, label, claim="C1"):
    return {"name": name, "state": state, "label": label, "claim": claim, "main": 1, "pr": 1 if state == "same" else 2}


def _sum(*obs):
    return probes.summarize([{"id": "p", "observations": list(obs)}])


def test_unchanged_sibling_is_advisory_when_input_differs():
    s = _sum(_o("c1.case1.title", "differs", P), _o("c1.case1.rel", "same", NH))
    assert s["flagged"] == [] and s["advisory_unchanged_subchecks"] == ["c1.case1.rel"]
    assert "advisory only" in s["reason"]


def test_input_with_no_difference_still_needs_attention():
    s = _sum(_o("c1.case1.title", "differs", P), _o("c1.case2.rel", "same", NH), _o("c1.case2.title", "same", NH))
    assert sorted(f["name"] for f in s["flagged"]) == ["c1.case2.rel", "c1.case2.title"]


def test_no_differing_value_still_needs_attention():
    s = _sum(_o("c1.case1.rel", "same", NH))
    assert [f["name"] for f in s["flagged"]] == ["c1.case1.rel"]


def test_other_claim_or_undotted_names_do_not_count():
    s = _sum(_o("c1.case1.title", "differs", P, "C1"), _o("c1.case1.rel", "same", NH, "C2"))
    assert [f["name"] for f in s["flagged"]] == ["c1.case1.rel"]
    s = _sum(_o("tc1_out", "differs", P), _o("tc2_out", "same", NH))
    assert [f["name"] for f in s["flagged"]] == ["tc2_out"]


def test_contradictions_and_unclaimed_differences_unchanged():
    s = _sum(_o("c1.case1.title", "differs", P), _o("c1.case1.x", "differs", FindingLabel.FALSE_CLAIM.value),
             _o("c1.case1.y", "differs", FindingLabel.UNMENTIONED_CHANGE.value, None))
    assert len(s["flagged"]) == 2


def test_requests_7520_record_no_longer_needs_attention():
    rec = json.loads((FX / "requests-7520.json").read_text())
    pp = dr.rejudge_probes(rec["probes"])
    assert pp["summary"]["flagged"] == [] and pp["summary"]["advisory_unchanged_subchecks"] == ["c2.case1.rel_present"]
    assert derive_verdict(rec, rec.get("baseline"), pp) != "needs_attention"


def test_rich_4147_record_still_needs_attention():
    rec = json.loads((FX / "rich-4147.json").read_text())
    assert derive_verdict(copy.deepcopy(rec), rec.get("baseline")) == "needs_attention"
