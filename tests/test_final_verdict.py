"""One final verdict: record.json, the reviewer report and the summary must agree (poc/final_verdict.py).

The fixture is a real product-route record (pallets/click#3896) whose probes were rewritten once. At run time an
unclaimed difference from a probe with no linked claims was advisory, so the verdict was could_not_verify. The
probe-rewrite cap re-derived the verdict from the pre-rewrite probes without re-applying the claim clean-up, lost the
advisory mark and lowered the record to needs_attention, while the report re-applied only the coverage gate and showed
could_not_verify."""
import copy
import json
from pathlib import Path

import pytest

from evals.checks import derive_verdict
from ops import daily_run
from poc import final_verdict
from reports import pr_report

FIX = Path(__file__).parent / "fixtures" / "final_verdict" / "click_3896_record.json"


def _rec():
    return json.loads(FIX.read_text())


def _ungated(rec):
    out = {k: v for k, v in rec.items()
           if not k.endswith(("_before_coverage_gate", "_before_ai_probe_gate", "_before_broken_probe_gate",
                              "_before_no_evidence_gate", "_before_advisory_gate"))
           and k not in ("probe_rewrite_cap", "coverage_gate")}
    out["verdict"], out["reason"] = rec["verdict_before_coverage_gate"], rec["reason_before_coverage_gate"]
    return out


def test_replayed_click_record_keeps_advisory_difference_and_is_could_not_verify():
    rec = _rec()
    assert rec["coverage_gate"]["changed"] is False          # the coverage gate never moved this verdict
    assert derive_verdict(daily_run.without_rewrite(rec), rec.get("baseline")) == "could_not_verify"
    assert derive_verdict(rec, rec.get("baseline")) == "could_not_verify"
    replayed = daily_run.gate(_ungated(rec))
    assert replayed["verdict"] == "could_not_verify"
    assert replayed["probe_rewrite_cap"]["without_rewrite"] == "could_not_verify"


def test_report_shows_exactly_the_record_verdict():
    rec = _rec()
    for v in ("needs_attention", "could_not_verify", "verified"):
        r = dict(rec, verdict=v)
        assert pr_report.normalize(copy.deepcopy(r))["verdict"] == v


def test_self_check_flags_disagreement():
    rec = _rec()
    assert final_verdict.disagreements([(rec, final_verdict.label(rec["verdict"]))]) == []
    bad = final_verdict.disagreements([(dict(rec, verdict="needs_attention"), "COULD NOT VERIFY")])
    assert bad and "record.json says NEEDS ATTENTION but the report shows COULD NOT VERIFY" in bad[0]


def test_render_run_fails_when_report_and_record_disagree(tmp_path, monkeypatch):
    run = tmp_path / "run"
    (run / "click-3896").mkdir(parents=True)
    (run / "click-3896" / "record.json").write_text(json.dumps(dict(_rec(), verdict="needs_attention")))
    real = pr_report.decide
    monkeypatch.setattr(pr_report, "decide", lambda rec, chk: dict(real(rec, chk), verdict="COULD NOT VERIFY",
                                                                 trust_override=False))
    with pytest.raises(pr_report.VerdictMismatch):
        pr_report.render_run(run, tmp_path / "out", formats=("md",))


def test_legacy_record_without_gate_block_is_still_gated():
    rec = _ungated(_rec())
    assert not final_verdict.is_final(rec)
    assert "coverage_gate" in final_verdict.final(rec)


# Verdict order: needs_attention is the strictest, then could_not_verify, then verified.
_ORDER = ["needs_attention", "could_not_verify", "verified"]


def test_verdict_rank_order():
    r = daily_run.VERDICT_RANK
    assert r["needs_attention"] < r["could_not_verify"] < r["verified"]


@pytest.mark.parametrize("a", _ORDER)
@pytest.mark.parametrize("b", _ORDER)
def test_lower_verdict_keeps_the_stricter(a, b):
    want = _ORDER[min(_ORDER.index(a), _ORDER.index(b))]
    assert daily_run.lower_verdict(a, b) == want == daily_run.lower_verdict(b, a)


@pytest.mark.parametrize("got", _ORDER)
@pytest.mark.parametrize("without", _ORDER)
def test_cap_rewrite_never_softens(got, without, monkeypatch):
    import evals.checks as checks
    monkeypatch.setattr(daily_run, "without_rewrite", lambda rec: rec)
    monkeypatch.setattr(checks, "derive_verdict", lambda rec, baseline=None: without)
    rec = {"verdict": got, "reason": "r", "probes": {"items": [], "rewrite": {"before": []}}}
    out = daily_run.cap_rewrite(rec)
    want = _ORDER[min(_ORDER.index(got), _ORDER.index(without))]
    assert out["verdict"] == want
    assert _ORDER.index(out["verdict"]) <= _ORDER.index(got)
    assert out["probe_rewrite_cap"] == {"with_rewrite": got, "without_rewrite": without, "final": want}


def test_keep_advisory_only_marks_unmentioned_changes():
    """The carried-over advisory mark never reaches a difference a claim covers, so a claimed contradiction still
    flags needs_attention."""
    from poc import probes
    old = {"observations": [{"name": "a", "advisory": True}, {"name": "b", "advisory": True}]}
    new = {"observations": [{"name": "a", "label": probes.FindingLabel.UNMENTIONED_CHANGE.value},
                            {"name": "b", "label": probes.FindingLabel.FALSE_CLAIM.value}]}
    out = daily_run._keep_advisory(old, new)["observations"]
    assert out[0].get("advisory") is True
    assert "advisory" not in out[1]
