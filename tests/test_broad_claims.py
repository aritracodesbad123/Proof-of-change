"""Broad 'nothing else changes' claims need several varied inputs (poc/broad_claims.py, product checks only)."""
import copy
import json
from pathlib import Path

from ops import daily_run as dr
from poc import broad_claims, model_probes, probes
from poc.model_provider import PROBES_PROMPT

FX = Path(__file__).resolve().parent / "fixtures/product_claims_2026_10_27"


def test_phrases():
    for t in ["The regex is updated while preserving existing behavior.", "Existing behavior for other tags is preserved.",
              "Nothing else changes.", "No other behaviour changes.", "no regressions", "Everything else stays the same.",
              "Output is otherwise unchanged.", "This does not affect other callers.", "without affecting other inputs"]:
        assert broad_claims.is_broad(t), t
    for t in ["Adds a flag.", "now returns a list", "Fixes adjacent tags.", "results are unchanged for seed 3", None, ""]:
        assert not broad_claims.is_broad(t), t


def test_broad_ids_only_same_claims():
    cl = [{"id": "C1", "text": "nothing else changes", "expect": "same"},
          {"id": "C2", "text": "nothing else changes", "expect": "differs"},
          {"id": "C3", "text": "adds a flag", "expect": "same"}]
    assert broad_claims.broad_ids(cl) == ["C1"]
    assert "C1" in broad_claims.probe_rule(cl) and str(broad_claims.MIN_INPUTS) in broad_claims.probe_rule(cl)
    assert broad_claims.probe_rule(cl[1:]) == ""


def _pr(n):
    obs = [{"name": f"C1.in{i}", "claim": "C1", "state": "same", "main": i, "pr": i, "label": "proven"}
           for i in range(n)]
    return {"items": [{"id": "model-p1", "source": "model",
                       "claims": [{"id": "C1", "text": "Existing behavior is preserved.", "expect": "same",
                                   "covers": ["C1.*"]}], "observations": obs}]}


def test_apply_holds_back_few_inputs_and_never_mutates():
    one = _pr(1)
    orig = copy.deepcopy(one)
    out = broad_claims.apply(one)
    assert one == orig
    assert out["broad_claims"]["held_back"] == ["C1"] and out["broad_claims"]["inputs"] == {"C1": 1}
    assert broad_claims.apply(_pr(broad_claims.MIN_INPUTS))["broad_claims"]["held_back"] == []
    assert broad_claims.apply(out)["broad_claims"] == out["broad_claims"]   # idempotent
    assert broad_claims.apply({"items": []}) == {"items": []}


def test_verdict_lowered_only_from_verified():
    held = broad_claims.apply(_pr(1))
    same = {"t::a": ("passed", ""), "t::b": ("passed", "")}
    cmp = dr.compare_sides({"main": [same] * 3, "pr": [same] * 3})
    ok = dr.verdict_for(cmp, None, probe_results=broad_claims.apply(_pr(3)))
    low = dr.verdict_for(cmp, None, probe_results=held)
    assert low[0] == "could_not_verify" and "broad_claim_few_inputs" in low[2] and "fewer than" in low[1]
    assert ok[0] != "could_not_verify" or "broad_claim_few_inputs" not in ok[2]


def test_rich_4147_record_no_longer_verified_on_one_input():
    r = json.loads((FX / "rich-4147.json").read_text())
    rec = {"probes": copy.deepcopy(r["probes"]), "product_check": True}
    dr.settle_probes(rec)
    assert "C3" in rec["probes"]["broad_claims"]["held_back"] and rec["broad_claims_note"]


def test_study_route_unchanged():
    r = json.loads((FX / "rich-4147.json").read_text())
    study = {"probes": copy.deepcopy(r["probes"])}
    dr.settle_probes(study)
    assert "broad_claims" not in study["probes"] and "broad_claims_note" not in study
    assert "Broad claims" not in PROBES_PROMPT and "Broad claims" not in model_probes.PRODUCT_PROBE_RULES
