"""Probes that link no claim: the retry is sent the claim list with ids and must name one per probe (no auto-link).
Built from the rich #4147 live check on c4a4ae9: claim C1 plus probe model-p1 with claims: []."""
import copy
import json
from pathlib import Path

from ops import daily_run
from poc import final_verdict, model_probes, model_provider

FX = Path(__file__).parent / "fixtures" / "unlinked_retry"
REC = json.loads((FX / "rich_4147_record.json").read_text())
CODE = (FX / "rich_4147_model-p1_code.py.txt").read_text()
CLAIMS = {"claims": [dict(c) for c in REC["probe_plan"]["model_claims"]]}
UNLINKED = {"probes": [{"id": "model-p1", "about": "", "claims": [], "code": CODE}]}
NAMES_C1 = {"probes": [{"id": "model-p1", "about": "", "code": CODE,
                        "claims": [{"id": "C1", "covers": ["c1.*"], "expect": "differs"}]}]}
TITLE = "Fix greedy regex merging adjacent tags"
BODY = "\n".join(c["source_quote"] for c in CLAIMS["claims"])


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


def _judge(claims):
    p = copy.deepcopy(REC["probes"])
    p["items"][0]["claims"] = claims
    return final_verdict.final(dict(REC, probes=daily_run.rejudge_probes(p, True)))["verdict"]


def test_retry_is_sent_the_claim_ids_and_the_one_id_per_probe_rule(tmp_path):
    prov, out = _run(tmp_path, [UNLINKED, NAMES_C1])
    retry = prov.prompts[-1][1]
    assert [t for t, _ in prov.prompts] == ["claims", "probes", "probes"]
    for c in CLAIMS["claims"]:
        assert f"- {c['id']} (expect {c['expect']}):" in retry
    assert "Every probe must list at least one of these claim ids" in retry
    assert out["retried"]["why"] == [model_probes.UNLINKED_REASON]


def test_rich_4147_probe_is_linked_to_c1_after_the_retry_but_not_verified(tmp_path):
    _, out = _run(tmp_path, [UNLINKED, NAMES_C1])
    assert "kept_first_answer" not in out["retried"]
    (x,) = out["probes"]
    assert "'claims': [{'id': 'C1'" in x["path"].read_text()
    assert _judge([]) != "verified"
    assert _judge([{"id": "C1", "covers": ["c1.*"], "expect": "differs"}]) != "verified"


def test_retry_naming_no_claim_keeps_differences_advisory(tmp_path):
    _, out = _run(tmp_path, [UNLINKED, copy.deepcopy(UNLINKED)])
    assert out["retried"]["kept_first_answer"] == "the retry linked no claim either"
    (x,) = out["probes"]
    assert "'claims': []" in x["path"].read_text()
    p = daily_run.rejudge_probes(copy.deepcopy(REC["probes"]), True)
    assert "with no linked claims shown as advisory only" in p["summary"]["reason"]
    assert p["summary"]["proven_claims"] == []


def test_retry_with_an_unlinked_probe_is_not_kept(tmp_path):
    mixed = {"probes": [NAMES_C1["probes"][0], dict(UNLINKED["probes"][0], id="p2")]}
    _, out = _run(tmp_path, [UNLINKED, mixed])
    assert out["retried"]["kept_first_answer"] == "a retry probe named no claim id"


def test_retry_naming_an_unknown_claim_id_is_not_kept(tmp_path):
    bad = {"probes": [dict(NAMES_C1["probes"][0], claims=[{"id": "C9", "covers": ["c1.*"], "expect": "differs"}])]}
    _, out = _run(tmp_path, [UNLINKED, bad])
    assert out["retried"].get("kept_first_answer")
    assert "'claims': []" in out["probes"][0]["path"].read_text()


def test_retry_with_fewer_probes_is_not_kept(tmp_path):
    two = {"probes": [UNLINKED["probes"][0], dict(UNLINKED["probes"][0], id="p2")]}
    _, out = _run(tmp_path, [two, NAMES_C1])
    assert out["retried"]["kept_first_answer"] == "the retry had fewer usable probes"
