"""A probe claim that expects a difference, and matches no observation, is never verified.

Synthetic fixtures only. The rule can lower verified to could_not_verify. It leaves every other verdict as it was.
"""
from ops.daily_run import compare_sides, verdict_for
from poc import probes


def _cmp_verified():
    same = {"t::a": ("passed", ""), "t::b": ("passed", "")}
    return compare_sides({"main": [same] * 3, "pr": [same] * 3})


def _probe(claims, main, pr):
    spec = {"id": "p", "target": "o/r#1", "about": "x", "claims": claims}
    item = probes.entry(spec, {"main": [main] * 3, "pr": [pr] * 3}, {"main": ["m"], "pr": ["p"]}, [], "library", None)
    return {"status": "ran", "items": [item]}


DIFFERS_MISSING = [{"id": "C9", "text": "the score changes", "covers": ["gone.*"], "expect": "differs"}]


def test_unmatched_differs_claim_is_names_only():
    item = _probe(DIFFERS_MISSING, {"r": 1}, {"r": 1})["items"][0]
    assert probes.unmatched_differs_claims({"items": [item]}) == ["C9"]
    hit = [{"id": "C1", "text": "the score changes", "covers": ["r"], "expect": "differs"}]
    assert probes.unmatched_differs_claims(_probe(hit, {"r": 1}, {"r": 2})) == []


def test_verified_becomes_could_not_verify_when_a_differs_claim_matches_nothing():
    v, reason, fl = verdict_for(_cmp_verified(), None, probe_results=_probe(DIFFERS_MISSING, {"r": 1}, {"r": 1}))
    assert v == "could_not_verify"
    assert "C9" in reason and "expect a difference but no observation matches" in reason
    assert "unmatched_differs_claim" in fl
    assert v != "verified"


def test_a_matched_differs_claim_that_does_differ_stays_verified():
    claims = [{"id": "C1", "text": "the score changes", "covers": ["r"], "expect": "differs"}]
    probed = _probe(claims, {"r": 1}, {"r": 2})
    probed["items"][0]["probe_changed_line_coverage"] = {
        "status": "measured", "changed_lines_total": 2, "changed_lines_covered": 1, "adequacy": "adequate"}
    v, reason, _ = verdict_for(_cmp_verified(), None, probe_results=probed)
    assert v == "verified" and "C1 proven" in reason


def test_other_verdicts_are_held():
    # A real difference is still needs attention, even when another claim matches nothing.
    claims = DIFFERS_MISSING + [{"id": "C2", "text": "other", "covers": ["also-missing"], "expect": "differs"}]
    v, reason, _ = verdict_for(_cmp_verified(), None, probe_results=_probe(claims, {"c": 1}, {"c": 2}))
    assert v == "needs_attention" and "c differs" in reason
    # A run that already could not verify stays there, with its original reason.
    held, held_reason, _ = verdict_for(None, "source build failed", probe_results=_probe(DIFFERS_MISSING, {"r": 1}, {"r": 1}))
    assert held == "could_not_verify" and held_reason.startswith("source build failed")
    assert "no observation matches" not in held_reason


def test_same_claim_with_no_match_is_not_this_rule():
    """Expecting 'same' is the behaviour-claim rule, not this one. With no behaviour claim the tests stand."""
    claims = [{"id": "C1", "text": "results stay", "covers": ["gone.*"], "expect": "same"}]
    assert verdict_for(_cmp_verified(), None, probe_results=_probe(claims, {"r": 1}, {"r": 1}))[0] == "verified"
