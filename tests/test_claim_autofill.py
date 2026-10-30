"""Blank probe claim ids are filled from the known testable claims (product checks only).

The saved miss left three probes with no claim ids, so they were rejected before past-boundary inputs could be
added and the check was could_not_verify. Filling those ids keeps the probes claim-linked. Replaying the saved
past-boundary outputs of the same two commits then reaches needs_attention from a false claim. No model call and
no project run.
"""
import ast
import copy
import json
import types
from pathlib import Path

import ops.daily_run as dr
from poc import boundary_claims as bc
from poc import boundary_probes, claim_hygiene, model_probes, probes
from poc.final_verdict import final

MISS = Path(__file__).parent / "fixtures" / "claim_autofill" / "rich-4147-live191"
FORCED = Path(__file__).parent / "fixtures" / "boundary_force" / "rich-4147-live188"
LIVE = json.loads((MISS / "record.json").read_text())
OUTS = json.loads((FORCED / "forced_outputs.json").read_text())
DIFF = (MISS / "pr.diff").read_text()
CLAIMS = LIVE["probe_plan"]["model_claims"]
TITLE = CLAIMS[0]["source_quote"]
BODY = "\n".join(c["source_quote"] for c in CLAIMS)


def _code(key, text):
    return ("from rich.highlighter import ReprHighlighter\n"
            f"inputs = {{'{key}': '{text}'}}\n"
            "obs = {}\n"
            "for name, raw in inputs.items():\n"
            "    obs[f'c1.{name}_spans'] = len(raw)\n"
            "print(1)\n")


PROBES = {"probes": [
    {"id": "p1", "about": "one tag", "claims": [], "code": _code("single", "<a>foo</a>")},
    {"id": "p2", "about": "adjacent tags", "claims": [],
     "code": _code("adjacent", "<a>content1</a><b>content2</b>")},
    {"id": "p3", "about": "spaced tags", "claims": [], "code": _code("spaced", "<a>foo</a> <b>bar</b>")},
]}


class _P:
    name = "fake"
    models = {"probes": "m"}

    def __init__(self, answers):
        self.answers = list(answers)

    def describe(self):
        return "fake"

    def complete_json(self, kind, prompt, user, schema, ctx):
        if kind == "claims":
            return {"claims": [dict(c) for c in CLAIMS]}
        return self.answers.pop(0) if self.answers else {"probes": []}


def _gen(tmp_path, answers, monkeypatch):
    monkeypatch.setattr(model_probes.freeze, "base_inputs", lambda *a, **k: {})
    monkeypatch.setattr(model_probes.freeze, "freeze", lambda *a, **k: {})
    monkeypatch.setattr(model_probes.freeze, "generator", lambda *a, **k: {"label": "x"})
    base = tmp_path / "base"
    (base / "rich").mkdir(parents=True)
    (base / "rich" / "highlighter.py").write_text("class ReprHighlighter:\n    pass\n")
    return model_probes.generate(_P(answers), "Textualize/rich", 4147, TITLE, BODY,
                                 {"rich/highlighter.py": base / "rich" / "highlighter.py"}, base, [],
                                 tmp_path / "out", product=True, diff=DIFF)


def _spec(path):
    line = next(ln for ln in path.read_text().splitlines() if ln.startswith("PROBE = "))
    return ast.literal_eval(line[len("PROBE = "):])


def _cmp():
    return dr.compare_sides({"main": [{"t::a": ("passed", "")}] * 3, "pr": [{"t::a": ("passed", "")}] * 3})


def test_saved_miss_rejected_three_blank_probes():
    plan = LIVE["probe_plan"]
    assert LIVE["verdict"] == "could_not_verify" and LIVE["probes"]["items"] == []
    assert plan["errors"] == [f"probe {pid!r} rejected: {model_probes.UNLINKED_PROBE}" for pid in ("p1", "p2", "p3")]
    assert [c["id"] for c in plan["model_claims"]] == ["C1", "C2", "C3"]
    assert plan["model_boundary_rule"] == boundary_probes.modified_patterns(DIFF)
    assert plan["model_boundary_rule"][0]["file"] == "rich/highlighter.py"
    assert plan["model_boundary_rule"][0]["line"] == 85
    blob = (MISS / "record.json").read_text() + DIFF
    assert "/home/" not in blob and "/Users/" not in blob and "/opt/" not in blob


def test_three_blank_probes_are_filled_and_get_past_boundary_inputs(tmp_path, monkeypatch):
    out = _gen(tmp_path, [PROBES], monkeypatch)
    assert not any(model_probes.UNLINKED_PROBE in e for e in out["errors"])
    assert [x["id"] for x in out["claims_filled"]] == ["p1", "p2", "p3"]
    assert all(x["claims"] == ["C1", "C2", "C3"] for x in out["claims_filled"])
    assert set(out["forced_boundary_inputs"]) == {"p1", "p2", "p3"}
    for pid, key in (("p1", "single"), ("p2", "adjacent"), ("p3", "spaced")):
        assert out["forced_boundary_inputs"][pid] == [f"{key}_pb_space", f"{key}_pb_text", f"{key}_pb_newline"]
    specs = [_spec(x["path"]) for x in out["probes"]]
    assert [[c["id"] for c in s["claims"]] for s in specs] == [["C1", "C2", "C3"]] * 3
    assert [c["expect"] for c in specs[0]["claims"]] == ["differs", "same", "differs"]


def test_an_unknown_claim_id_is_still_rejected(tmp_path, monkeypatch):
    bad = {"probes": [{"id": "p1", "about": "x", "code": _code("single", "<a>foo</a>"),
                       "claims": [{"id": "C9", "covers": ["C9.*"], "expect": "differs"}]}]}
    out = _gen(tmp_path, [bad, bad], monkeypatch)
    assert out["probes"] == [] and "claims_filled" not in out
    assert any("C9" in e for e in out["errors"])


def test_a_named_claim_is_not_expanded_and_a_blank_entry_is_dropped(tmp_path, monkeypatch):
    mixed = {"probes": [{"id": "p1", "about": "x", "code": _code("single", "<a>foo</a>"),
                         "claims": [{"id": "C1", "covers": ["C1.*"], "expect": "differs"}, {"id": ""}]}]}
    out = _gen(tmp_path, [mixed], monkeypatch)
    assert "claims_filled" not in out and len(out["probes"]) == 1
    assert [c["id"] for c in _spec(out["probes"][0]["path"])["claims"]] == ["C1"]


def test_filled_covers_that_match_no_observation_stay_advisory():
    """A filled claim links names that start with its id. A difference under any other name stays advisory and
    does not raise needs attention. The claim still expected a difference, so the check is not verified."""
    item = {"id": "model-p1", "source": "model", "target": "Textualize/rich#4147", "about": "spans",
            "claims": [{"id": "C1", "text": CLAIMS[0]["text"], "covers": ["C1.*"], "expect": "differs",
                        "source": "PR description"}],
            "runs": {"main": [{"spans": 8}] * 3, "pr": [{"spans": 2}] * 3}}
    pr = claim_hygiene.apply({"items": [probes.rejudge_entry(item)]})
    obs = pr["items"][0]["observations"][0]
    assert obs["advisory"] is True and obs["label"] == "unmentioned"
    assert probes.summarize(pr["items"])["flagged"] == []
    v, _, fl = dr.verdict_for(_cmp(), None, None, {"all": ["rich/highlighter.py"]}, pr, None, "full")
    assert v == "could_not_verify" and "unmatched_differs_claim" in fl


def test_plan_records_the_filled_ids(tmp_path, monkeypatch):
    def fake_generate(*a, **k):
        return {"probes": [], "claims": [], "rejected_claims": [], "errors": [],
                "claims_filled": [{"id": "p1", "claims": ["C1", "C2", "C3"]}]}

    monkeypatch.setattr(dr.model_probes, "generate", fake_generate)
    monkeypatch.setattr(dr.probes, "find_probes", lambda *a: [])
    rec = {}
    a = types.SimpleNamespace(baseline=None, model_note=None, provider=object(), product_check=True, pr=4147,
                              bench=None, no_probes=False)
    dr.plan_probes("Textualize/rich", {"pr": 4147, "title": TITLE, "body": BODY, "files": {"all": []}, "diff": DIFF},
                   rec, tmp_path, [], tmp_path, a)
    assert rec["probe_plan"]["model_claims_filled"] == [{"id": "p1", "claims": ["C1", "C2", "C3"]}]


def _replay():
    """The saved past-boundary outputs, with claim ids filled from the miss's known claims."""
    rec = json.loads((FORCED / "record.json").read_text())
    rec.pop("coverage_gate", None)
    rec["probe_plan"]["model_claims"] = [dict(c) for c in CLAIMS]
    rec["probe_plan"]["model_boundary_rule"] = LIVE["probe_plan"]["model_boundary_rule"]
    it = rec["probes"]["items"][0]
    it["path"] = "model-probes/model-probe1.forced.py.txt"
    keep = set(bc.probe_inputs((FORCED / it["path"]).read_text()))
    obs = {s: {k: v for k, v in OUTS[s].items() if bc.input_for(k, {n: "" for n in keep})} for s in ("main", "pr")}
    it["runs"] = {s: [copy.deepcopy(obs[s]) for _ in range(3)] for s in ("main", "pr")}
    filled = model_probes.fill_blank_claims({"id": "probe1", "about": "x", "code": "x = 1\n", "claims": []}, CLAIMS)
    by_id = {c["id"]: c for c in CLAIMS}
    it["claims"] = [{"id": c["id"], "text": by_id[c["id"]]["text"], "covers": list(c["covers"]),
                     "expect": c["expect"], "source": "PR description"} for c in filled["claims"]]
    items = probes.link_across_probes([probes.rejudge_entry(x) for x in rec["probes"]["items"]])
    rec["probes"] = claim_hygiene.apply(dict(rec["probes"], items=items, summary=probes.summarize(items)))
    return final(dr.rejudge(rec, FORCED))


def test_after_fill_the_saved_past_boundary_outputs_need_attention():
    f = _replay()
    assert f["verdict"] == "needs_attention"
    flagged = f["probes"]["summary"]["flagged"]
    kept = [x for x in flagged if x["label"] == "false_claim" and "_pb_" in x["name"]
            and str(x.get("claim") or "").endswith("-kept")]
    assert kept
    assert "C3-kept" in {c["id"] for c in f["probes"]["boundary_claims"]["seeded"]}
