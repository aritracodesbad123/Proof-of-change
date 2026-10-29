"""Seeded "behaviour kept" claim for inputs just past an edited pattern's old match boundary (poc/boundary_claims)."""
import copy
import json
from pathlib import Path

import pytest

import ops.daily_run as dr
from poc import boundary_claims as bc
from poc import claim_hygiene, probes
from poc.final_verdict import final

FX = Path(__file__).parent / "fixtures"
CASE = FX / "boundary_claims" / "rich-4147"
OUTS = json.loads((FX / "inert_probe" / "rich4147_fixed_probe_outputs.json").read_text())["probes"]
OLD = r"(?P<tag_start><)(?P<tag_name>[-\w.:|]*)(?P<tag_contents>[\w\W]*)(?P<tag_end>>)"
RULE = [{"file": "rich/highlighter.py", "line": 85, "old": OLD}]


def _replay(link_model_claims=False):
    """The live record with the hand-fixed probes' real outputs, claims as the model wrote them unless asked, through
    the live settle step (claim hygiene), then rejudge + final()."""
    rec = json.loads((CASE / "record.json").read_text())
    rec.pop("coverage_gate", None)
    cl = {c["id"]: c for c in rec["probe_plan"]["model_claims"]}
    for it in rec["probes"]["items"]:
        c = it["id"].rsplit("-", 1)[-1]
        it["runs"] = copy.deepcopy(OUTS[c]["fixed"])
        if link_model_claims:
            cid = c.upper()
            it["claims"] = [{"id": cid, "text": cl[cid]["text"], "covers": [f"{cid}.*"], "expect": cl[cid]["expect"]}]
            it["runs"] = {s: [{k.replace(f"{c}.", f"{cid}."): v for k, v in r.items()} for r in rs]
                          for s, rs in it["runs"].items()}
    items = probes.link_across_probes([probes.rejudge_entry(it) for it in rec["probes"]["items"]])
    rec["probes"] = claim_hygiene.apply(dict(rec["probes"], items=items, summary=probes.summarize(items)))
    return final(dr.rejudge(rec, CASE))


def _false(f):
    got = [x["name"].split(".")[1] for x in f["probes"]["summary"]["flagged"] if x["label"] == "false_claim"]
    assert len(got) == 2 * len(set(got))  # both probes, each input once
    return sorted(set(got))


PAST = ["followed", "newline", "pre_newline", "preceded"]


def test_replay_as_written_reaches_needs_attention_without_links():
    f = _replay()
    assert f["verdict"] == "needs_attention"
    assert _false(f) == PAST
    assert f["probes"]["boundary_claims"]["seeded"][0]["id"] == "C3-kept"


def test_replay_with_model_links_is_no_longer_verified():
    f = _replay(link_model_claims=True)
    assert f["verdict"] == "needs_attention" and _false(f) == PAST


def test_replay_without_the_seeded_claim_is_what_it_was(monkeypatch):
    monkeypatch.setattr(bc, "apply", lambda p, r, d: p)
    assert _replay()["verdict"] == "could_not_verify"
    assert _replay(link_model_claims=True)["verdict"] == "verified"


def test_the_claimed_change_itself_is_not_flagged():
    f = _replay(link_model_claims=True)
    names = {x["name"].split(".")[1] for x in f["probes"]["summary"]["flagged"] if x.get("claim") == "C3-kept"}
    assert "adjacent" not in names and "single" not in names


@pytest.mark.parametrize("text,want", [
    ("<a>content</a>zz", True), ("xx<a>content</a>yy", True), ("<a>content</a> ", True),
    ("<Widget>\nnext", True), ("<Widget>\n", False), ("<a>content</a>", False),
    ("<a>content1</a><b>content2</b>", False), ("no tag here", False)])
def test_past_boundary(text, want):
    assert bc.past_boundary(text, [OLD]) is want


def test_seed_needs_rule_testable_preserve_and_not_a_pr_test_rerun():
    c = {"id": "C3", "text": "Updated to handle adjacent tags while preserving existing behavior.", "testable": True}
    assert [s["id"] for s in bc.seed([c], RULE)] == ["C3-kept"]
    assert bc.seed([c], []) == []
    assert bc.seed([dict(c, testable=False)], RULE) == []
    assert bc.seed([dict(c, text="Adjacent tags are now split.")], RULE) == []
    assert bc.seed([dict(c, text="test_adjacent_tags passes while preserving existing behavior.")], RULE,
                   {"test_adjacent_tags"}) == []
    assert bc.seed([dict(c, text="The new test passes and existing behaviour is preserved.")], RULE) == []


def test_same_observation_is_left_untouched_and_nothing_is_proven():
    it = {"id": "p", "path": "model-probes/model-probe-c1.py.txt", "observations": [
        {"name": "c1.followed", "state": "same", "label": "no_difference", "claim": None},
        {"name": "c1.preceded", "state": "differs", "label": "unmentioned", "claim": None}]}
    rec = {"product_check": True, "probe_plan": {"model_boundary_rule": RULE, "model_claims": [
        {"id": "C3", "text": "while preserving existing behavior", "testable": True}]}}
    out = bc.apply({"items": [it]}, rec, CASE)
    assert out["items"][0]["observations"][0]["label"] == "no_difference"
    assert out["items"][0]["observations"][1]["label"] == "false_claim"
    assert out["boundary_claims"]["flagged"] == ["p c1.preceded"]
    assert all(o["label"] != "proven" for o in out["items"][0]["observations"])


def test_live_settle_step_applies_it():
    it = {"id": "p", "path": "model-probes/model-probe-c1.py.txt", "observations": [
        {"name": "c1.followed", "state": "differs", "label": "unmentioned", "claim": None}]}
    rec = {"product_check": True, "probes": {"items": [it]}, "probe_plan": {"model_boundary_rule": RULE,
           "model_claims": [{"id": "C3", "text": "keeps the existing behaviour", "testable": True}]}}
    dr.settle_boundary_claims(rec, CASE)
    assert rec["probes"]["items"][0]["observations"][0]["label"] == "false_claim"


def test_study_route_is_untouched():
    rec = json.loads((CASE / "record.json").read_text())
    rec["product_check"] = False
    p = {"items": [{"id": "x"}]}
    assert bc.apply(p, rec, CASE) is p


def test_probe_inputs_reads_only_string_tables():
    src = (CASE / "model-probes" / "model-probe-c1.py.txt").read_text()
    got = bc.probe_inputs(src)
    assert got["followed"] == "<a>content</a>zz" and "adjacent" in got
    assert bc.probe_inputs("x = {'a': 1}") == {} and bc.probe_inputs("def (") == {}
