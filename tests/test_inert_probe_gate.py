"""Inert-probe guard: a probe whose every value is empty on both sides is no evidence (rich#4147, 2026-10-29)."""
import json
from pathlib import Path

from ops.daily_run import all_inert, gate, inert_probe_gate

FIX = Path(__file__).parent / "fixtures" / "inert_probe" / "rich4147_live_all_empty.json"


def _rec():
    return json.loads(FIX.read_text())


def test_live_all_empty_record_is_not_verified():
    rec = _rec()
    assert rec["verdict"] == "verified"
    assert all(all_inert(it) for it in rec["probes"]["items"])
    out = inert_probe_gate(rec)
    assert out["verdict"] == "could_not_verify"
    assert out["reason"].startswith("could not verify: broken probe")
    assert out["verdict_before_inert_probe_gate"] == "verified"
    assert inert_probe_gate(out) == out


def test_full_gate_chain_trips_on_live_pattern():
    assert gate(_rec())["verdict"] == "could_not_verify"


def test_one_non_empty_value_anywhere_is_not_inert():
    rec = _rec()
    rec["probes"]["items"][0]["runs"]["pr"][2]["c1.followed"] = [[0, 1, "repr.tag_start"]]
    assert not all_inert(rec["probes"]["items"][0])
    rec2 = _rec()
    rec2["probes"]["items"][1]["observations"][0]["main"] = [[0, 1, "repr.tag_start"]]
    assert inert_probe_gate(rec2)["verdict"] == "verified"


def test_never_raises_and_needs_items():
    rec = _rec()
    rec["verdict"] = "needs_attention"
    assert inert_probe_gate(rec)["verdict"] == "needs_attention"
    assert inert_probe_gate({"verdict": "verified", "probes": {"items": []}})["verdict"] == "verified"
    assert not all_inert({"observations": []})


def test_scalar_zero_and_false_are_values_not_empty():
    item = {"observations": [{"main": 0, "pr": False}], "runs": {}}
    assert not all_inert(item)


def test_prompt_rule_mentions_return_value_and_claim_ids():
    from poc.model_probes import PRODUCT_PROBE_RULES
    assert "t = h(Text(s))" in PRODUCT_PROBE_RULES and "returns a new" in PRODUCT_PROBE_RULES
    assert "claim ids" in PRODUCT_PROBE_RULES


PROOF = Path(__file__).parent / "fixtures" / "inert_probe" / "rich4147_fixed_probe_outputs.json"
PAST_BOUNDARY = ("followed", "preceded")  # a tag followed (or preceded) by text: past the old rule's boundary


def _tags(spans):
    return [s for s in spans if s[2].startswith("repr.tag_")]


def test_offline_proof_original_probes_are_inert_on_both_sides():
    d = json.loads(PROOF.read_text())
    for c, kinds in d["probes"].items():
        item = {"observations": [{"main": [], "pr": []}], "runs": kinds["orig"]}
        assert all_inert(item), c


def test_offline_proof_fixed_probes_see_tags_on_main_and_none_on_pr():
    d = json.loads(PROOF.read_text())
    for c, kinds in d["probes"].items():
        for inp in PAST_BOUNDARY:
            key = f"{c}.{inp}"
            for run in kinds["fixed"]["main"]:
                assert _tags(run[key]), (key, "main")
            for run in kinds["fixed"]["pr"]:
                assert run[key] and not _tags(run[key]), (key, "pr")
    assert d["rejudge"]["orig_as_run"]["verdict"] == "could_not_verify"
    assert d["rejudge"]["fixed_linked_preserve_claim"]["verdict"] == "needs_attention"
    assert any(f["label"] == "false_claim" and f["name"] == "C3.followed"
               for f in d["rejudge"]["fixed_linked_preserve_claim"]["flagged"])
