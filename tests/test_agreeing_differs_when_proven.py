"""A differs claim whose covered observations all agree is advisory when another differs claim is already proven.

The two fixtures are the probe runs from loguru pull request 1536 and toolz pull request 654, trimmed to the
fields the verdict reads. Nothing from those pull requests is run again.
"""
import copy
import json
from pathlib import Path

from evals.checks import derive_verdict
from ops import daily_run as dr
from poc import probes
from poc.verdict import FindingLabel

FX = Path(__file__).resolve().parent / "fixtures/agreeing_differs"
PHRASE = "claim not shown on these inputs; a related change was proven"
P, NH = FindingLabel.PROVEN.value, FindingLabel.NEEDS_HUMAN.value


def _load(name):
    return json.loads((FX / name).read_text())


def _rejudge(rec):
    return dr.rejudge_probes(rec["probes"], bool(rec.get("product_check")), broad_gate=dr.broad_gate_for(rec))


def _verdict(rec, pp=None):
    pp = _rejudge(rec) if pp is None else pp
    return dr.verdict_for(rec.get("comparison"), None, rec.get("exit_check"), rec.get("files"), pp,
                          rec.get("behaviour_claims"), rec.get("baseline"))


def _o(name, state, label, claim="C1"):
    return {"name": name, "state": state, "label": label, "claim": claim,
            "main": 1, "pr": 1 if state == "same" else 2}


def _sum(*obs):
    return probes.summarize([{"id": "p", "observations": list(obs)}])


def _agree_on_pr(rec, names):
    """Make named observations the same on both sides, so the differs claim they covered is no longer proven."""
    rec = copy.deepcopy(rec)
    for it in rec["probes"]["items"]:
        runs = it.get("runs") or {}
        for run_m, run_p in zip(runs.get("main") or [], runs.get("pr") or []):
            for name in names:
                if name in run_m:
                    run_p[name] = copy.deepcopy(run_m[name])
    return rec


def test_agreeing_claim_is_advisory_when_a_differs_claim_is_proven():
    s = _sum(_o("c1.out", "differs", P, "C1"), _o("c3.a", "same", NH, "C3"), _o("c3.b", "same", NH, "C3"))
    assert s["flagged"] == []
    assert s["advisory_agreeing_differs"] == ["c3.a", "c3.b"]
    assert s["proven_claims"] == ["C1"]
    assert PHRASE in s["reason"]
    assert "need attention" not in s["reason"]


def test_nothing_proven_still_needs_attention():
    s = _sum(_o("c3.a", "same", NH, "C3"))
    assert [f["name"] for f in s["flagged"]] == ["c3.a"]
    assert s["advisory_agreeing_differs"] == []
    assert PHRASE not in s["reason"]
    assert "does not differ although the claim says it does" in s["reason"]


def test_proven_same_claim_does_not_count():
    s = _sum(_o("c1.out", "same", P, "C1"), _o("c3.a", "same", NH, "C3"))
    assert [f["name"] for f in s["flagged"]] == ["c3.a"]
    assert PHRASE not in s["reason"]


def test_partly_shown_claim_still_needs_attention():
    s = _sum(_o("c1.out", "differs", P, "C1"),
             _o("c2.case1.out", "differs", P, "C2"),
             _o("c2.case2.out", "same", NH, "C2"))
    assert [f["name"] for f in s["flagged"]] == ["c2.case2.out"]
    assert s["advisory_agreeing_differs"] == []


def test_contradictions_stay_flagged():
    false = _o("c2.out", "differs", FindingLabel.FALSE_CLAIM.value, "C2")
    unclaimed = _o("extra", "differs", FindingLabel.UNMENTIONED_CHANGE.value, None)
    mixed = _o("c3.bad", "differs", FindingLabel.FALSE_CLAIM.value, "C3")
    sibling = _o("c3.ok", "same", NH, "C3")
    unstable = {"name": "c4.out", "state": "flaky", "label": NH, "claim": "C4", "pr_only": "regression",
                "main": 1, "pr": 2}
    s = _sum(_o("c1.out", "differs", P, "C1"), false, unclaimed, mixed, sibling, unstable)
    assert sorted(f["name"] for f in s["flagged"]) == ["c2.out", "c3.bad", "c3.ok", "c4.out", "extra"]
    assert s["advisory_agreeing_differs"] == []


def test_probe_broken_sibling_is_not_all_agree():
    broken = {"name": "c3.err", "state": "same", "label": FindingLabel.NOT_TESTABLE.value, "claim": "C3",
              "main": {"raises": "TypeError"}, "pr": {"raises": "TypeError"}}
    s = _sum(_o("c1.out", "differs", P, "C1"), _o("c3.ok", "same", NH, "C3"), broken)
    assert [f["name"] for f in s["flagged"]] == ["c3.ok"]


def test_loguru_1536_agreeing_claims_do_not_need_attention():
    rec = _load("loguru-1536.json")
    pp = _rejudge(rec)
    summary = pp["summary"]
    assert summary["proven_claims"] == ["C1", "C2"]
    assert summary["advisory_unchanged_subchecks"] == ["c1.case2", "c1.case3"]
    assert summary["advisory_agreeing_differs"] == ["c3.case2", "c4.case3"]
    assert summary["flagged"] == []
    assert PHRASE in summary["reason"]
    assert "does not differ although the claim says it does" not in summary["reason"]
    v, reason, _ = _verdict(rec, pp)
    assert v == "verified" and PHRASE in reason and "need attention" not in reason
    assert derive_verdict(rec, rec["baseline"], pp) == "verified"


def test_loguru_1536_without_a_proven_differs_claim_still_needs_attention():
    rec = _agree_on_pr(_load("loguru-1536.json"), ["c1.case1", "c2.case1"])
    pp = _rejudge(rec)
    flagged = sorted(f["name"] for f in pp["summary"]["flagged"])
    assert "c3.case2" in flagged and "c4.case3" in flagged
    assert pp["summary"]["advisory_agreeing_differs"] == []
    assert pp["summary"]["proven_claims"] == []
    v, reason, _ = _verdict(rec, pp)
    assert v == "needs_attention"
    assert "does not differ although the claim says it does" in reason
    assert PHRASE not in reason


def test_toolz_654_agreeing_claims_do_not_need_attention():
    rec = _load("toolz-654.json")
    pp = _rejudge(rec)
    summary = pp["summary"]
    assert summary["proven_claims"] == ["C4"]
    assert summary["advisory_agreeing_differs"] == ["c1.order", "c3.order", "c5.pass_count"]
    assert summary["flagged"] == []
    assert PHRASE in summary["reason"]
    assert "could not run on either side" in summary["reason"]
    v, reason, _ = _verdict(rec, pp)
    assert v == "verified" and PHRASE in reason and "need attention" not in reason
    assert derive_verdict(rec, rec["baseline"], pp) == "verified"


def test_toolz_654_without_a_proven_differs_claim_still_needs_attention():
    rec = _agree_on_pr(_load("toolz-654.json"), ["c4.result"])
    pp = _rejudge(rec)
    flagged = sorted(f["name"] for f in pp["summary"]["flagged"])
    assert flagged == ["c1.order", "c3.order", "c4.result", "c5.pass_count"]
    assert pp["summary"]["advisory_agreeing_differs"] == []
    v, reason, _ = _verdict(rec, pp)
    assert v == "needs_attention" and PHRASE not in reason
