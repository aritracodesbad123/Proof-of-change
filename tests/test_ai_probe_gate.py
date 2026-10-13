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


def test_other_verdicts_and_tests_only_mode_untouched():
    assert dr.ai_probe_gate(_rec([], verdict="needs_attention"))["verdict"] == "needs_attention"
    assert dr.ai_probe_gate(_rec([], baseline="tests"))["verdict"] == "verified"


def test_idempotent():
    once = dr.ai_probe_gate(_rec([]))
    assert dr.ai_probe_gate(once) == once
