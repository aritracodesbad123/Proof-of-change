"""Probes that link no claim: the retry is sent the claim list with ids and must name one per probe (no auto-link).
Built from the rich #4147 live check on c4a4ae9: claims C1 (differs) and C2 (same), probe model-p1 with claims: [].
Verdicts are recomputed with ops.daily_run.rejudge_probes and verdict_for from the saved probe runs and the saved
test comparison, never read back from the saved record."""
import ast
import copy
import json
from pathlib import Path

from ops import daily_run
from poc import model_probes, model_provider

FX = Path(__file__).parent / "fixtures" / "unlinked_retry"
REC = json.loads((FX / "rich-4147" / "record.jsonl").read_text())
CODE = (FX / "rich_4147_model-p1_code.py.txt").read_text()
CLAIMS = {"claims": [dict(c) for c in REC["probe_plan"]["model_claims"]]}
C1 = {"id": "C1", "covers": ["c1.*"], "expect": "differs"}
UNLINKED = {"probes": [{"id": "model-p1", "about": "", "claims": [], "code": CODE}]}
TITLE = "Fix greedy regex merging adjacent tags"
BODY = "\n".join(c["source_quote"] for c in CLAIMS["claims"])


def _answer(*claims):
    return {"probes": [{"id": "model-p1", "about": "", "code": CODE, "claims": [dict(c) for c in claims]}]}


class Scripted(model_provider.Provider):
    name = "scripted"

    def __init__(self, answers):
        super().__init__()
        self.answers, self.prompts = list(answers), []

    def complete_json(self, task, system, user, schema, ctx):
        self.prompts.append((task, user))
        return CLAIMS if task == "claims" else self.answers.pop(0)


def _run(tmp_path, answers):
    base = tmp_path / "base"
    (base / "rich").mkdir(parents=True)
    (base / "rich" / "highlighter.py").write_text("class ReprHighlighter:\n    pass\n")
    prov = Scripted(answers)
    out = model_probes.generate(prov, "Textualize/rich", 4147, TITLE, BODY,
                                {"rich/highlighter.py": base / "rich" / "highlighter.py"}, base, [tmp_path / "pr"],
                                tmp_path / "out")
    return prov, out


def _frozen_claims(out):
    (x,) = out["probes"]
    line = next(ln for ln in x["path"].read_text().splitlines() if ln.startswith("PROBE = "))
    return ast.literal_eval(line[len("PROBE = "):])["claims"]


TESTS = "83 test(s) ran on main, 84 on the PR; 1 new test(s) pass, 83 unchanged"


def _judge(claims):
    """The saved #4147 run's verdict, reason and flags, its probe linked to the given claims."""
    p = copy.deepcopy(REC["probes"])
    p["items"][0]["claims"] = [dict(c) for c in claims]
    pr = daily_run.rejudge_probes(p, bool(REC.get("product_check")), broad_gate=daily_run.broad_gate_for(REC))
    return daily_run.verdict_for(REC["comparison"], None, REC["exit_check"], REC.get("files"), pr,
                                 REC.get("behaviour_claims"), REC.get("baseline"))


SUB = ("probe: {n} unchanged sub-check(s) of an input where the claim's change was seen, shown as advisory only: "
       "c1.attrs_spancount (C1); c1.attrs_spans (C1); c1.none_spancount (C1); c1.none_spans (C1)")
C2_DIFFS = "c2.adjacent_spancount, c2.adjacent_spans, c2.nested_spancount, c2.nested_spans"


def test_saved_unlinked_run_is_could_not_verify():
    v, reason, fl = _judge([])
    assert v == "could_not_verify" and "advisory_unclaimed_difference" in fl
    assert reason == ("could not verify: probe(s) model-p1 have no linked claims and saw a difference no claim covers, "
                      f"so the change is not confirmed ({TESTS}; probe: 8 difference(s) from a probe with no linked "
                      "claims shown as advisory only; probe: 12 other observation(s) identical on both sides)")


def test_c1_covering_c1_only_names_the_uncovered_differences():
    # The probe records the same inputs again under c2.*; linking C1 to c1.* leaves those uncovered, so the
    # differences stay advisory and the check is not verified. The reason names them, not "no linked claims".
    v, reason, fl = _judge([C1])
    assert v == "could_not_verify" and "advisory_unclaimed_difference" in fl
    named = ", ".join(f"model-p1 {n}" for n in C2_DIFFS.split(", "))
    assert reason == (f"could not verify: difference(s) no linked claim covers ({named}), so the change is not "
                      f"confirmed ({TESTS}; probe: 4 difference(s) no linked claim covers, shown as advisory only: "
                      f"{C2_DIFFS}; {SUB.format(n=6)}; probe: claim(s) C1 proven; probe: 6 other observation(s) "
                      "identical on both sides)")


def test_fully_covered_differences_are_verified():
    v, reason, fl = _judge([dict(C1, covers=["c1.*", "c2.*"])])
    assert v == "verified" and "advisory_unclaimed_difference" not in fl
    assert reason == f"{TESTS}; {SUB.format(n=12)}; probe: claim(s) C1 proven"


def test_retry_is_sent_the_claim_ids_and_the_rule(tmp_path):
    prov, out = _run(tmp_path, [UNLINKED, _answer(C1)])
    retry = prov.prompts[-1][1]
    assert [t for t, _ in prov.prompts] == ["claims", "probes", "probes"]
    for c in CLAIMS["claims"]:
        assert f"- {c['id']} (expect {c['expect']}):" in retry
    assert "Every probe must list at least one of these claim ids" in retry
    assert out["retried"]["why"] == [model_probes.UNLINKED_REASON]


def test_retry_naming_c1_is_kept_and_linked_but_not_verified(tmp_path):
    _, out = _run(tmp_path, [UNLINKED, _answer(C1)])
    assert "kept_first_answer" not in out["retried"]
    claims = _frozen_claims(out)
    assert [c["id"] for c in claims] == ["C1"]
    assert _judge(claims)[0] == "could_not_verify"


def test_retry_naming_no_claim_keeps_differences_advisory(tmp_path):
    _, out = _run(tmp_path, [UNLINKED, copy.deepcopy(UNLINKED)])
    assert out["retried"]["kept_first_answer"] == "the retry linked no claim either"
    assert _frozen_claims(out) == []
    assert _judge([])[0] == "could_not_verify"


def test_retry_with_an_unlinked_probe_is_not_kept(tmp_path):
    mixed = {"probes": [_answer(C1)["probes"][0], dict(UNLINKED["probes"][0], id="p2")]}
    _, out = _run(tmp_path, [UNLINKED, mixed])
    assert out["retried"]["kept_first_answer"] == "a retry probe named no claim id"


def test_retry_naming_an_unknown_claim_id_is_not_kept(tmp_path):
    _, out = _run(tmp_path, [UNLINKED, _answer(dict(C1, id="C9"))])
    assert out["retried"].get("kept_first_answer")
    assert _frozen_claims(out) == []


def test_retry_with_fewer_probes_is_not_kept(tmp_path):
    two = {"probes": [UNLINKED["probes"][0], dict(UNLINKED["probes"][0], id="p2")]}
    _, out = _run(tmp_path, [two, _answer(C1)])
    assert out["retried"]["kept_first_answer"] == "the retry had fewer usable probes"


def test_cover_retry_still_needs_fewer_unmatched_covers(tmp_path):
    # The #177 cover retry is unchanged: a linked probe whose cover names nothing the code records is retried, and
    # a retry with as many unmatched covers is not kept.
    miss = _answer(dict(C1, covers=["zz.missing"]))
    prov, out = _run(tmp_path, [miss, copy.deepcopy(miss)])
    assert [t for t, _ in prov.prompts] == ["claims", "probes", "probes"]
    assert out["retried"]["kept_first_answer"] == "the retry did not leave fewer unmatched covers"
    assert out["unmatched_covers"] == ["C1:zz.missing"]
