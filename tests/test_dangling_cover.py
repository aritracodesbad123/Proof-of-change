"""A probe's only claim whose covers match none of its observation names (poc/probes._dangling_cover_link)."""
from poc import probes

FL = probes.FindingLabel


def _judge(claims, main, pr, pr_runs=None):
    spec = {"id": "model-p1", "source": "model", "claims": claims}
    runs = {"main": [main] * 3, "pr": pr_runs or [pr] * 3}
    return {o["name"]: o for o in probes.judge(spec, runs)}


ONE = [{"id": "C2", "text": "filter is now applied", "covers": ["C2"], "expect": "differs"}]


def test_only_claim_with_dangling_cover_makes_difference_advisory_not_proven():
    o = _judge(ONE, {"calls": 0}, {"calls": 2})["calls"]
    assert o["label"] == FL.UNMENTIONED_CHANGE.value and o["advisory"] and o["linked_by"] == "dangling_cover"


def test_claimless_probe_unchanged():
    o = _judge([], {"calls": 0}, {"calls": 2})["calls"]
    assert o["label"] == FL.UNMENTIONED_CHANGE.value and not o.get("advisory")


def test_cover_that_matches_something_keeps_other_differences_flagged():
    claims = [{"id": "C1", "text": "a now differs", "covers": ["a"], "expect": "differs"}]
    o = _judge(claims, {"a": 1, "b": 1}, {"a": 2, "b": 2})
    assert o["a"]["label"] == FL.PROVEN.value and not o["b"].get("advisory")


def test_several_claims_or_same_claim_unchanged():
    two = ONE + [{"id": "C3", "text": "x", "covers": ["C3"], "expect": "differs"}]
    assert not _judge(two, {"calls": 0}, {"calls": 2})["calls"].get("advisory")
    same = [dict(ONE[0], expect="same")]
    assert not _judge(same, {"calls": 0}, {"calls": 2})["calls"].get("advisory")


def test_pr_unstable_difference_not_linked():
    o = _judge(ONE, {"calls": 0}, None, [{"calls": 2}, {"calls": 3}, {"calls": 0}])["calls"]
    assert not o.get("advisory")
