"""Never 'verified' in AI-probe modes unless an AI-written probe executed a changed line."""
from ops import daily_run as dr


def _rec(items, baseline="full", verdict="verified"):
    return {"verdict": verdict, "reason": "tests same", "baseline": baseline, "probes": {"items": items}}


def _probe(source, covered):
    return {"id": f"{source}-1", "source": source, "probe_changed_line_coverage": {"changed_lines_covered": covered}}


def test_verified_needs_a_model_probe_on_changed_lines():
    out = dr.ai_probe_gate(_rec([_probe("diff", 3)]))
    assert out["verdict"] == "could_not_verify" and out["verdict_before_ai_probe_gate"] == "verified"
    assert "no AI-written probe" in out["reason"]


def test_model_probe_that_ran_changed_lines_keeps_verified():
    assert dr.ai_probe_gate(_rec([_probe("model", 2)]))["verdict"] == "verified"


def test_model_probe_that_missed_changed_lines_does_not_count():
    assert dr.ai_probe_gate(_rec([_probe("model", 0)]))["verdict"] == "could_not_verify"


def _proven(name="c1.changed"):
    return {"name": name, "label": "proven", "state": "differs", "claim": "C1"}


def test_an_unmeasured_probe_that_showed_the_claimed_difference_counts_when_tests_covered_every_line():
    item = {"id": "model-1", "source": "model", "status": "ran", "observations": [_proven()]}
    rec = _rec([item])
    rec["coverage"] = {"status": "measured", "changed_lines_total": 4, "changed_lines_covered": 4}
    assert dr.ai_probe_gate(rec)["verdict"] == "verified"


def test_an_unmeasured_probe_without_a_claimed_difference_does_not_count():
    item = {"id": "model-1", "source": "model", "status": "ran", "observations": [
        {"name": "c1.control", "label": "needs_human", "state": "same", "claim": "C1"}]}
    rec = _rec([item])
    rec["coverage"] = {"status": "measured", "changed_lines_total": 4, "changed_lines_covered": 4}
    assert dr.ai_probe_gate(rec)["verdict"] == "could_not_verify"


def test_a_measured_zero_still_does_not_count_when_the_probe_saw_a_difference():
    item = _probe("model", 0) | {"status": "ran", "observations": [_proven()]}
    rec = _rec([item])
    rec["coverage"] = {"status": "measured", "changed_lines_total": 4, "changed_lines_covered": 4}
    assert dr.ai_probe_gate(rec)["verdict"] == "could_not_verify"


def test_partial_test_coverage_does_not_excuse_a_missing_probe_line_count():
    item = {"id": "model-1", "source": "model", "status": "ran", "observations": [_proven()]}
    rec = _rec([item])
    rec["coverage"] = {"status": "measured", "changed_lines_total": 4, "changed_lines_covered": 2}
    assert dr.ai_probe_gate(rec)["verdict"] == "could_not_verify"


def test_other_verdicts_and_tests_only_mode_untouched():
    assert dr.ai_probe_gate(_rec([], verdict="needs_attention"))["verdict"] == "needs_attention"
    assert dr.ai_probe_gate(_rec([], baseline="tests"))["verdict"] == "verified"


def test_idempotent():
    once = dr.ai_probe_gate(_rec([]))
    assert dr.ai_probe_gate(once) == once
