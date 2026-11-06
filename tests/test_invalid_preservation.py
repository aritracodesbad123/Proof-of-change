"""A contradicted part of an explicit preservation claim is advisory when it is the proven change.

The general fixture follows a recorded check in which one call's return stayed True and the next call's
return went from True to False, while a differs claim's count of true returns went from 2 to 1. The
phrase-off fixture is those saved run values and claim texts, with the recorded target removed. Nothing
here names a repository, and nothing from a pull request is run again.
"""
import json
from pathlib import Path

from evals.checks import derive_verdict
from ops.daily_run import broad_gate_for, compare_sides, rejudge_probes, verdict_for
from poc import probes
from poc.probes import _PRESERVATION_RE, INVALID_PRESERVATION_NOTE
from poc.verdict import FindingLabel
from tests.test_same_input_guard import _judge, _load, _without_cross_run

FX = Path(__file__).resolve().parent / "fixtures" / "invalid_preservation"

P = FindingLabel.PROVEN.value
FALSE = FindingLabel.FALSE_CLAIM.value
NH = FindingLabel.NEEDS_HUMAN.value

PRESERVE = ("The method returns True exactly when at least one condition evaluates to True, "
            "preserving the documented contract.")


def _cmp_ok():
    same = {"t::a": ("passed", "")}
    return compare_sides({"main": [same] * 3, "pr": [same] * 3})


_COV = {"status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1, "adequacy": "adequate"}


def _item(claims, main, pr, pid="model-p1"):
    spec = {"id": pid, "target": "o/r#1", "about": "returns", "claims": claims, "source": "model"}
    item = probes.entry(spec, {"main": [main] * 3, "pr": [pr] * 3}, None, [], "model", None)
    item["status"] = "ran"
    item["probe_changed_line_coverage"] = dict(_COV)
    return item


def _checked(claims, main, pr):
    item = _item(claims, main, pr)
    pp = rejudge_probes({"status": "ran", "items": [item]}, False)
    summary = pp["summary"]
    verdict = verdict_for(_cmp_ok(), None, None, None, pp)
    return pp, summary, verdict


def _rotation_claims():
    return [
        {"id": "C1", "text": "After the change every condition is invoked.", "expect": "differs",
         "covers": ["c1.limit_after_first"]},
        {"id": "C2", "text": PRESERVE, "expect": "same", "covers": ["c2.ret_msg1", "c2.ret_msg2"]},
        {"id": "C4", "text": "Fewer calls return True after the fix.", "expect": "differs",
         "covers": ["c4.num_true_returns"]},
    ]


def _rotation_sides(second=False, count=1, first_limit="later"):
    main = {"c1.limit_after_first": None, "c2.ret_msg1": True, "c2.ret_msg2": True, "c4.num_true_returns": 2}
    pr = {"c1.limit_after_first": first_limit, "c2.ret_msg1": True, "c2.ret_msg2": second,
          "c4.num_true_returns": count}
    return main, pr


def test_preservation_part_that_is_the_proven_count_is_advisory():
    main, pr = _rotation_sides()
    pp, summary, (verdict, reason, _) = _checked(_rotation_claims(), main, pr)
    obs = {o["name"]: o for o in pp["items"][0]["observations"]}
    assert obs["c2.ret_msg2"]["label"] == FALSE and obs["c2.ret_msg2"]["state"] == "differs"
    assert obs["c2.ret_msg1"]["label"] == P
    assert obs["c4.num_true_returns"]["label"] == P
    assert summary["flagged"] == []
    assert summary["advisory_invalid_preservation"] == ["c2.ret_msg2"]
    assert INVALID_PRESERVATION_NOTE in summary["reason"]
    assert "need attention" not in summary["reason"]
    assert verdict == "verified"
    assert INVALID_PRESERVATION_NOTE in reason
    assert "need attention" not in reason


def test_second_message_should_rotate_and_the_new_code_does_not():
    """The second call should rotate and stays False. A proven change on that same input does not clear it."""
    claims = [
        {"id": "D", "text": "The second message now rotates.", "expect": "differs", "covers": ["turn.second"]},
        {"id": "M", "text": "The limit on that same call moves forward.", "expect": "differs",
         "covers": ["turn.limit"]},
    ]
    main = {"turn.second": False, "turn.limit": 0}
    pr = {"turn.second": False, "turn.limit": 1}
    _pp, summary, (verdict, reason, _) = _checked(claims, main, pr)
    assert [f["name"] for f in summary["flagged"]] == ["turn.second"]
    assert summary["advisory_invalid_preservation"] == []
    assert verdict == "needs_attention"
    assert "does not differ although the claim says it does" in reason


def test_unmentioned_return_is_not_excused_by_a_linked_preservation_part():
    claims = _rotation_claims()
    main, pr = _rotation_sides()
    main["other.flag"] = False
    pr["other.flag"] = True
    _pp, summary, (verdict, reason, _) = _checked(claims, main, pr)
    assert summary["advisory_invalid_preservation"] == ["c2.ret_msg2"]
    assert [f["name"] for f in summary["flagged"]] == ["other.flag"]
    assert verdict == "needs_attention"
    assert "other.flag differs and no claim covers it" in reason


def test_proven_claims_plus_an_unrelated_difference_are_not_a_blanket_pass():
    claims = [
        {"id": "C1", "text": "The first result changes.", "expect": "differs", "covers": ["c1.out"]},
        {"id": "C2", "text": "The second result changes.", "expect": "differs", "covers": ["c2.out"]},
        {"id": "C4", "text": "The fourth result changes.", "expect": "differs", "covers": ["c4.out"]},
        {"id": "K", "text": PRESERVE, "expect": "same", "covers": ["k.left", "k.right"]},
    ]
    main = {"c1.out": 1, "c2.out": 3, "c4.out": 5, "k.left": True, "k.right": True}
    pr = {"c1.out": 2, "c2.out": 4, "c4.out": 6, "k.left": True, "k.right": False}
    _pp, summary, (verdict, _reason, _) = _checked(claims, main, pr)
    assert [f["name"] for f in summary["flagged"]] == ["k.right"]
    assert summary["advisory_invalid_preservation"] == []
    assert summary["proven_claims"] == ["C1", "C2", "C4", "K"]
    assert verdict == "needs_attention"


def test_still_rejected_is_not_excused_by_other_proven_claims():
    claims = [
        {"id": "C1", "text": "A parsed amount changes.", "expect": "differs", "covers": ["c1.result"]},
        {"id": "C8", "text": "Old results are still rejected.", "expect": "same", "covers": ["c8.*"]},
    ]
    main = {"c1.result": 1, "c8.error": 60.0}
    pr = {"c1.result": 2, "c8.error": "ValueError"}
    _pp, summary, (verdict, reason, _) = _checked(claims, main, pr)
    assert [f["name"] for f in summary["flagged"]] == ["c8.error"]
    assert summary["advisory_invalid_preservation"] == []
    assert verdict == "needs_attention"
    assert "c8.error differs although the claim says it does not" in reason


def test_every_preservation_part_changing_stays_needs_attention():
    claims = _rotation_claims()
    main = {"c1.limit_after_first": None, "c2.ret_msg1": True, "c2.ret_msg2": True, "c4.num_true_returns": 2}
    pr = {"c1.limit_after_first": "later", "c2.ret_msg1": False, "c2.ret_msg2": False, "c4.num_true_returns": 0}
    _pp, summary, (verdict, _reason, _) = _checked(claims, main, pr)
    assert sorted(f["name"] for f in summary["flagged"]) == ["c2.ret_msg1", "c2.ret_msg2"]
    assert summary["advisory_invalid_preservation"] == []
    assert verdict == "needs_attention"


def test_mixed_wildcard_cover_stays_needs_attention():
    """Exact names beside a wildcard do not excuse the flip. The wildcard rejects the whole claim."""
    claims = _rotation_claims()
    claims[1] = dict(claims[1], covers=["c2.ret_msg1", "c2.ret_msg2", "c2.*"])
    main, pr = _rotation_sides()
    _pp, summary, (verdict, reason, _) = _checked(claims, main, pr)
    assert [f["name"] for f in summary["flagged"]] == ["c2.ret_msg2"]
    assert summary["advisory_invalid_preservation"] == []
    assert verdict == "needs_attention"
    assert "c2.ret_msg2 differs although the claim says it does not" in reason


def test_exact_count_on_a_different_probe_stays_needs_attention():
    """A 2-to-1 count on another probe, even with the same claim id, does not excuse this probe's flip."""
    claims = [c for c in _rotation_claims() if c["id"] != "C4"]
    main = {"c1.limit_after_first": None, "c2.ret_msg1": True, "c2.ret_msg2": True}
    pr = {"c1.limit_after_first": "later", "c2.ret_msg1": True, "c2.ret_msg2": False}
    own = _item(claims, main, pr, pid="model-p1")
    other = _item(
        [{"id": "C4", "text": "Fewer calls return True after the fix.", "expect": "differs",
          "covers": ["c4.num_true_returns"]}],
        {"c4.num_true_returns": 2}, {"c4.num_true_returns": 1}, pid="model-p2")
    pp = rejudge_probes({"status": "ran", "items": [own, other]}, False)
    assert [f["name"] for f in pp["summary"]["flagged"]] == ["c2.ret_msg2"]
    assert pp["summary"]["advisory_invalid_preservation"] == []
    verdict, reason, _ = verdict_for(_cmp_ok(), None, None, None, pp)
    assert verdict == "needs_attention"
    assert "c2.ret_msg2 differs although the claim says it does not" in reason


def test_same_probe_count_still_waives_beside_another_probe():
    main, pr = _rotation_sides()
    own = _item(_rotation_claims(), main, pr, pid="model-p1")
    other = _item(
        [{"id": "C4", "text": "A different count changes.", "expect": "differs",
          "covers": ["c4.num_true_returns"]}],
        {"c4.num_true_returns": 9}, {"c4.num_true_returns": 8}, pid="model-p2")
    pp = rejudge_probes({"status": "ran", "items": [own, other]}, False)
    assert pp["summary"]["advisory_invalid_preservation"] == ["c2.ret_msg2"]
    assert pp["summary"]["flagged"] == []
    verdict, reason, _ = verdict_for(_cmp_ok(), None, None, None, pp)
    assert verdict == "verified"
    assert INVALID_PRESERVATION_NOTE in reason


def test_frozen_phrase_removed_stays_needs_attention_and_c4_stays_proven():
    """Saved run values. Turning the preservation wording off puts the flip back to needs attention."""
    rec = json.loads((FX / "phrase_off.json").read_text())
    rec["comparison"] = _cmp_ok()
    turned = False
    for it in rec["probes"]["items"]:
        for claim in it.get("claims") or []:
            if claim.get("id") != "C2":
                continue
            assert _PRESERVATION_RE.search(claim["text"])
            claim["text"] = claim["text"].replace(
                ", preserving the documented 'any of which can trigger the rotation' contract", "")
            assert not _PRESERVATION_RE.search(claim["text"])
            turned = True
    assert turned
    pp = rejudge_probes(rec["probes"], bool(rec.get("product_check")), broad_gate=broad_gate_for(rec))
    obs = {o["name"]: o for it in pp["items"] for o in it["observations"]}
    assert obs["c4.num_true_returns"]["label"] == P and obs["c4.num_true_returns"]["state"] == "differs"
    assert obs["c2.ret_msg2"]["label"] == FALSE
    assert [f["name"] for f in pp["summary"]["flagged"]] == ["c2.ret_msg2"]
    assert pp["summary"]["advisory_invalid_preservation"] == []
    verdict, reason, _ = verdict_for(rec["comparison"], None, rec.get("exit_check"), rec.get("files"), pp,
                                     rec.get("behaviour_claims"), rec.get("baseline"))
    assert verdict == "needs_attention" and "c2.ret_msg2" in reason
    assert derive_verdict(rec, rec.get("baseline")) == "needs_attention"


def test_wildcard_cover_is_not_an_explicit_target():
    claims = _rotation_claims()
    claims[1] = dict(claims[1], covers=["c2.*"])
    main, pr = _rotation_sides()
    _pp, summary, (verdict, _reason, _) = _checked(claims, main, pr)
    assert [f["name"] for f in summary["flagged"]] == ["c2.ret_msg2"]
    assert summary["advisory_invalid_preservation"] == []
    assert verdict == "needs_attention"


def test_intended_count_that_does_not_change_leaves_the_disagreement():
    claims = _rotation_claims()
    main, pr = _rotation_sides(second=False, count=2)
    _pp, summary, (verdict, _reason, _) = _checked(claims, main, pr)
    assert [f["name"] for f in summary["flagged"]] == ["c2.ret_msg2"]
    assert summary["advisory_invalid_preservation"] == []
    assert verdict == "needs_attention"


def test_barcode_162_stays_needs_attention():
    spec = _without_cross_run(_load("barcode-162.json"))
    _files, _cmp, pp, (verdict, reason, flags) = _judge(spec)
    assert verdict == "needs_attention"
    assert "cross_run_settled" not in flags
    assert probes.summarize(pp["items"])["advisory_invalid_preservation"] == []
    assert "does not differ although the claim says it does" in reason
    assert NH == "needs_human"
