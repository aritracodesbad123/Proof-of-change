"""A probe whose claim patterns match none of its observation names does not count.

The reason is recorded on the probe. Red and amber observations are still reported, so the verdict cannot rise.
Synthetic fixtures only.
"""
from ops.daily_run import ai_probe_gate, compare_sides, verdict_for
from poc import behaviour_claims, probes


def _cmp_verified():
    same = {"t::a": ("passed", ""), "t::b": ("passed", "")}
    return compare_sides({"main": [same] * 3, "pr": [same] * 3})


def _item(claims, main, pr):
    spec = {"id": "p", "target": "o/r#1", "about": "x", "claims": claims}
    return probes.entry(spec, {"main": [main] * 3, "pr": [pr] * 3}, {"main": ["m"], "pr": ["p"]}, [], "library", None)


MISSES = [{"id": "C1", "text": "results unchanged", "covers": ["gone.*"], "expect": "same"}]
HITS = [{"id": "C1", "text": "results unchanged", "covers": ["r"], "expect": "same"}]
CLAIM = [{"source": "PR description", "quote": "Results are unchanged.", "pattern": "unchanged"}]
MEASURED = {"status": "measured", "changed_lines_total": 2, "changed_lines_covered": 1, "adequacy": "adequate"}


def test_patterns_that_miss_every_observation_are_rejected_and_the_reason_is_recorded():
    item = probes.classify_item(_item(MISSES, {"r": 1}, {"r": 1}))
    assert item["status"] == "rejected"
    assert "C1" in item["rejected_reason"] and "not counted" in item["rejected_reason"]
    applied = probes.apply_status({"status": "ran", "items": [_item(MISSES, {"r": 1}, {"r": 1})]})
    assert applied["status"] == "rejected"
    assert "not counted" in applied["summary"]["reason"]


def test_one_matching_pattern_keeps_the_probe():
    item = probes.classify_item(_item(HITS, {"r": 1}, {"r": 1}))
    assert item["status"] == "ran" and "rejected_reason" not in item
    both = HITS + [{"id": "C2", "text": "other", "covers": ["gone.*"], "expect": "differs"}]
    assert probes.classify_item(_item(both, {"r": 1}, {"r": 1}))["status"] == "ran"


def test_a_probe_with_no_claims_is_not_this_case():
    assert probes.classify_item(_item([], {"r": 1}, {"r": 1}))["status"] == "ran"
    assert probes.rejection_reason(_item([], {"r": 1}, {"r": 1})) is None


def test_a_rejected_probe_does_not_count_and_cannot_raise_the_verdict():
    green = _item(MISSES, {"r": 1}, {"r": 1})
    green["probe_changed_line_coverage"] = dict(MEASURED)
    assert not behaviour_claims.probe_covers({"items": [probes.classify_item(green)]})
    v, reason, _ = verdict_for(_cmp_verified(), None, probe_results={"items": [green]}, claims=CLAIM)
    assert v == "could_not_verify" and "unverified behaviour claim" in reason

    # No behaviour claim: the tests were already verified, and dropping the probe holds that.
    held = verdict_for(_cmp_verified(), None, probe_results={"items": [green]})
    assert held[0] == "verified"

    # A difference the probe did see is still needs attention. Rejecting the probe must not hide it.
    red = _item(MISSES, {"c": 1}, {"c": 2})
    red["probe_changed_line_coverage"] = dict(MEASURED)
    v, reason, _ = verdict_for(_cmp_verified(), None, probe_results={"items": [red]})
    assert v == "needs_attention" and "c differs" in reason


def test_a_rejected_model_probe_does_not_satisfy_the_ai_probe_gate():
    rejected = {"id": "model-1", "source": "model", "status": "rejected",
                "probe_changed_line_coverage": {"changed_lines_covered": 4}}
    out = ai_probe_gate({"verdict": "verified", "reason": "tests same", "baseline": "full",
                         "probes": {"items": [rejected]}})
    assert out["verdict"] == "could_not_verify"
    kept = {"id": "model-2", "source": "model", "status": "ran",
            "probe_changed_line_coverage": {"changed_lines_covered": 1}}
    assert ai_probe_gate({"verdict": "verified", "reason": "tests same", "baseline": "full",
                          "probes": {"items": [rejected, kept]}})["verdict"] == "verified"
    assert ai_probe_gate({"verdict": "needs_attention", "reason": "differs", "baseline": "full",
                          "probes": {"items": [rejected]}})["verdict"] == "needs_attention"
