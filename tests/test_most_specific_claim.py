"""An observation covered by several claims belongs to the most specific one (poc/probes.claim_for)."""
from poc import probes

FL = probes.FindingLabel


def _judge(claims, main, pr):
    spec = {"id": "model-p1", "source": "model", "claims": claims}
    runs = {"main": [main] * 3, "pr": [pr] * 3}
    return {o["name"]: o for o in probes.judge(spec, runs)}


def test_single_name_cover_beats_list():
    claims = [{"id": "C1", "text": "a and b stay the same", "covers": ["a", "b"], "expect": "same"},
              {"id": "C2", "text": "b now returns 2", "covers": ["b"], "expect": "differs"}]
    o = _judge(claims, {"a": 1, "b": 1}, {"a": 1, "b": 2})
    assert o["b"]["claim"] == "C2" and o["b"]["label"] == FL.PROVEN.value
    assert o["a"]["claim"] == "C1" and o["a"]["label"] == FL.PROVEN.value


def test_exact_name_beats_wildcard():
    claims = [{"id": "C1", "text": "x.* stays the same", "covers": ["x.*"], "expect": "same"},
              {"id": "C2", "text": "x.b now differs", "covers": ["x.b", "x.c"], "expect": "differs"}]
    assert probes.claim_for({"claims": claims}, "x.b")["id"] == "C2"
    assert probes.claim_for({"claims": claims}, "x.a")["id"] == "C1"


def test_contradiction_still_flags():
    claims = [{"id": "C1", "text": "a and b stay the same", "covers": ["a", "b"], "expect": "same"},
              {"id": "C2", "text": "b now returns 2", "covers": ["b"], "expect": "differs"}]
    o = _judge(claims, {"a": 1, "b": 1}, {"a": 5, "b": 2})
    assert o["a"]["label"] == FL.FALSE_CLAIM.value and not o["a"].get("advisory")


def test_tie_keeps_first_claim():
    claims = [{"id": "C1", "text": "b differs", "covers": ["b"], "expect": "differs"},
              {"id": "C2", "text": "b is new", "covers": ["b"], "expect": "differs"}]
    assert probes.claim_for({"claims": claims}, "b")["id"] == "C1"
