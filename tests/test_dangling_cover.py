"""A probe's only claim whose covers match none of its observation names (poc/probes._dangling_cover_link)."""
from poc import probes

FL = probes.FindingLabel


def _judge(claims, main, pr, pr_runs=None):
    spec = {"id": "model-p1", "source": "model", "claims": claims}
    runs = {"main": [main] * 3, "pr": pr_runs or [pr] * 3}
    return {o["name"]: o for o in probes.judge(spec, runs)}


ONE = [{"id": "C2", "text": "filter is now applied", "covers": ["result.filtered"], "expect": "differs"}]


def test_only_claim_with_dangling_cover_makes_difference_advisory_not_proven():
    o = _judge(ONE, {"result.calls": 0}, {"result.calls": 2})["result.calls"]
    assert o["label"] == FL.UNMENTIONED_CHANGE.value and o["advisory"] and o["linked_by"] == "dangling_cover"


def test_unrelated_difference_in_the_same_probe_stays_needs_attention():
    obs = _judge(ONE, {"result.calls": 0, "other.size": 1}, {"result.calls": 2, "other.size": 5})
    assert obs["result.calls"]["advisory"]
    o = obs["other.size"]
    assert o["label"] == FL.UNMENTIONED_CHANGE.value and not o.get("advisory")
    flagged = probes.summarize([{"id": "model-p1", "observations": list(obs.values())}])["flagged"]
    assert [f["name"] for f in flagged] == ["other.size"]


def test_name_sharing_a_cover_prefix_is_linked_but_a_bare_wildcard_links_nothing():
    claims = [{"id": "C1", "text": "x now differs", "covers": ["result.port_match"], "expect": "differs"}]
    assert _judge(claims, {"result.port": 0}, {"result.port": 1})["result.port"]["advisory"]
    star = [{"id": "C1", "text": "x now differs", "covers": ["*_never"], "expect": "differs"}]
    assert not _judge(star, {"calls": 0}, {"calls": 2})["calls"].get("advisory")


def test_claimless_probe_unchanged():
    o = _judge([], {"calls": 0}, {"calls": 2})["calls"]
    assert o["label"] == FL.UNMENTIONED_CHANGE.value and not o.get("advisory")


def test_cover_that_matches_something_keeps_other_differences_flagged():
    claims = [{"id": "C1", "text": "a now differs", "covers": ["a"], "expect": "differs"}]
    o = _judge(claims, {"a": 1, "b": 1}, {"a": 2, "b": 2})
    assert o["a"]["label"] == FL.PROVEN.value and not o["b"].get("advisory")


def test_several_claims_or_same_claim_unchanged():
    two = ONE + [{"id": "C3", "text": "x", "covers": ["result.other"], "expect": "differs"}]
    assert not _judge(two, {"result.calls": 0}, {"result.calls": 2})["result.calls"].get("advisory")
    same = [dict(ONE[0], expect="same")]
    assert not _judge(same, {"result.calls": 0}, {"result.calls": 2})["result.calls"].get("advisory")


def test_pr_unstable_difference_not_linked():
    o = _judge(ONE, {"result.calls": 0}, None, [{"result.calls": 2}, {"result.calls": 3}, {"result.calls": 0}])["result.calls"]
    assert not o.get("advisory")
