"""Forced past-boundary probe inputs and required claim ids (poc/boundary_claims.force_inputs, model_probes).

Offline proof on the live188 miss (rich#4147, 2026-10-30): the model's probe tested only inputs fully inside the old
match and named no claim id, so the run came out could_not_verify. With forced inputs (real outputs from rich base
9d8f9a3 and head 3bd56b5) and the probe tied to the model's own claim ids, the same record reaches needs_attention
from false_claim on past-boundary inputs."""
import ast
import copy
import json
from pathlib import Path

import pytest

import ops.daily_run as dr
from poc import boundary_claims as bc
from poc import claim_hygiene, model_probes, probes
from poc.final_verdict import final

CASE = Path(__file__).parent / "fixtures" / "boundary_force" / "rich-4147-live188"
OUTS = json.loads((CASE / "forced_outputs.json").read_text())
OLD = r"(?P<tag_start><)(?P<tag_name>[-\w.:|]*)(?P<tag_contents>[\w\W]*)(?P<tag_end>>)"
SRC = (CASE / "model-probes" / "model-probe1.py.txt").read_text()


def _replay(forced=True, linked=True):
    rec = json.loads((CASE / "record.json").read_text())
    rec.pop("coverage_gate", None)
    it = rec["probes"]["items"][0]
    it["path"] = "model-probes/" + ("model-probe1.forced.py.txt" if forced else "model-probe1.py.txt")
    keep = set(bc.probe_inputs((CASE / it["path"]).read_text()))
    obs = {s: {k: v for k, v in OUTS[s].items() if bc.input_for(k, {n: "" for n in keep})} for s in ("main", "pr")}
    if forced:   # real outputs of the forced probe; otherwise the live188 runs exactly as recorded
        it["runs"] = {s: [copy.deepcopy(obs[s]) for _ in range(3)] for s in ("main", "pr")}
    if linked:
        cl = {c["id"]: c for c in rec["probe_plan"]["model_claims"]}
        it["claims"] = [{"id": c, "text": cl[c]["text"], "covers": [f"{c.lower()}.*"], "expect": cl[c]["expect"]}
                        for c in ("C1", "C2")]   # the two "differs" claims; C3 (preserve) left to the seeded C3-kept claim
    items = probes.link_across_probes([probes.rejudge_entry(x) for x in rec["probes"]["items"]])
    rec["probes"] = claim_hygiene.apply(dict(rec["probes"], items=items, summary=probes.summarize(items)))
    return final(dr.rejudge(rec, CASE))


def _false(f):
    return sorted({x["name"] for x in f["probes"]["summary"]["flagged"] if x["label"] == "false_claim"})


def test_forced_inputs_turn_the_live188_miss_into_a_catch():
    f = _replay()
    assert f["verdict"] == "needs_attention"
    got = _false(f)
    assert got and all("_pb_" in n for n in got)
    assert any(n.endswith("single_pb_text_spans") for n in got)
    assert "C3-kept" in {c["id"] for c in f["probes"]["boundary_claims"]["seeded"]}


def test_past_boundary_values_are_real_and_differ():
    for k, v in OUTS["main"].items():
        if "_pb_" in k and k.endswith("_spans") and ".adjacent" not in k:
            assert v and len(v) > len(OUTS["pr"][k])   # tags on main, fewer on the PR side


def test_without_forced_inputs_the_miss_stays_a_miss():
    f = _replay(forced=False)
    assert not [n for n in _false(f) if "_pb_" in n] and not f["probes"]["boundary_claims"]["flagged"]


def test_unlinked_as_recorded_is_not_a_catch():
    f = _replay(forced=False, linked=False)
    assert f["verdict"] == "could_not_verify" and not _false(f)


def test_without_the_input_name_match_it_is_a_miss(monkeypatch):
    monkeypatch.setattr(bc, "input_for", lambda name, inputs: (str(name).rsplit(".", 1)[-1]
                                                               if str(name).rsplit(".", 1)[-1] in inputs else None))
    assert not _false(_replay())


def test_without_forcing_in_generate_no_inputs_are_added(monkeypatch, tmp_path):
    monkeypatch.setattr(bc, "force_inputs", lambda code, olds: (code, []))
    ok = {"probes": [{"id": "p1", "about": "x", "code": CODE,
                      "claims": [{"id": "C1", "covers": ["C1.*"], "expect": "differs"}]}]}
    out = _gen(tmp_path, [ok], monkeypatch)
    assert "forced_boundary_inputs" not in out


def test_force_inputs_rules():
    new, added = bc.force_inputs(SRC, [OLD])
    got = bc.probe_inputs(new)
    assert got["single_pb_newline"] == "<a>foo</a>\ntail" and got["single_pb_space"] == "<a>foo</a> tail"
    assert all(not v.endswith("\n") for v in got.values())   # never a bare trailing newline
    assert all(bc.past_boundary(got[n], [OLD]) for n in added)
    assert bc.force_inputs(SRC, []) == (SRC, [])            # no edited pattern: untouched
    assert bc.force_inputs("x = {'a': 'no tag'}", [OLD]) == ("x = {'a': 'no tag'}", [])
    assert bc.force_inputs(new, [OLD])[1] == []              # idempotent


class _P:
    name = "fake"
    models = {"probes": "m"}

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    def describe(self):
        return "fake"

    def complete_json(self, kind, prompt, user, schema, ctx):
        self.calls += 1
        if kind == "claims":
            return {"claims": [{"id": "C1", "text": "Adjacent tags are split.", "testable": True, "expect": "differs",
                                "source_quote": "Adjacent tags are split."}]}
        return self.answers.pop(0) if self.answers else {"probes": []}


CODE = "from m import f\ninputs = {'a': '<a>x</a>'}\nfor k, v in inputs.items():\n    print(f(v))\n"
DIFF = ("--- a/m.py\n+++ b/m.py\n@@ -1,1 +1,1 @@\n-P = r\"<[\\w\\W]*>\"\n+P = r\"<[\\w\\W]*?>(?=<|$)\"\n")


def _gen(tmp_path, answers, monkeypatch):
    monkeypatch.setattr(model_probes.freeze, "base_inputs", lambda *a, **k: {})
    monkeypatch.setattr(model_probes.freeze, "freeze", lambda *a, **k: {})
    monkeypatch.setattr(model_probes.freeze, "generator", lambda *a, **k: {"label": "x"})
    return model_probes.generate(_P(answers), "o/r", 1, "Adjacent tags are split.", "Adjacent tags are split.",
                                 {"m.py": "P = 1"}, tmp_path, [], tmp_path / "out", product=True, diff=DIFF)


def test_blank_claim_ids_are_filled_and_inputs_are_forced(tmp_path, monkeypatch):
    bare = {"probes": [{"id": "p1", "about": "x", "code": CODE, "claims": []}]}
    out = _gen(tmp_path, [bare, bare], monkeypatch)
    assert len(out["probes"]) == 1 and not any(model_probes.UNLINKED_PROBE in e for e in out["errors"])
    assert out["claims_filled"] == [{"id": "p1", "claims": ["C1"]}]
    assert out["forced_boundary_inputs"]["p1"] == ["a_pb_space", "a_pb_text", "a_pb_newline"]
    spec = ast.literal_eval(next(ln for ln in out["probes"][0]["path"].read_text().splitlines()
                                  if ln.startswith("PROBE = "))[len("PROBE = "):])
    assert [c["id"] for c in spec["claims"]] == ["C1"]


def test_blank_probe_is_still_rejected_when_it_cannot_be_filled(tmp_path, monkeypatch):
    monkeypatch.setattr(model_probes, "fill_blank_claims", lambda p, claims: p)
    bare = {"probes": [{"id": "p1", "about": "x", "code": CODE, "claims": []}]}
    out = _gen(tmp_path, [bare, bare], monkeypatch)
    assert out["probes"] == [] and any(model_probes.UNLINKED_PROBE in e for e in out["errors"])


def test_linked_probe_is_kept_and_gets_forced_inputs(tmp_path, monkeypatch):
    ok = {"probes": [{"id": "p1", "about": "x", "code": CODE,
                      "claims": [{"id": "C1", "covers": ["C1.*"], "expect": "differs"}]}]}
    out = _gen(tmp_path, [ok], monkeypatch)
    assert len(out["probes"]) == 1 and out["boundary_rule"]
    assert out["forced_boundary_inputs"]["p1"] == ["a_pb_space", "a_pb_text", "a_pb_newline"]


@pytest.mark.parametrize("name,want", [("c1.single_pb_text_spans", "single_pb_text"), ("c1.single", "single"),
                                       ("c1.single_spans", "single"), ("c1.other", None)])
def test_input_for(name, want):
    assert bc.input_for(name, {"single": "", "single_pb_text": ""}) == want
