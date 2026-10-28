"""Re-judging recomputes the broad-claims gate from current code instead of trusting the copy saved in the record."""
import copy

from ops import daily_run as dr
from poc import broad_claims


def _probes(n, saved=None):
    runs = {"main": [{f"C1.in{i}": i for i in range(n)}] * 3, "pr": [{f"C1.in{i}": i for i in range(n)}] * 3}
    item = {"id": "model-p1", "source": "model", "target": "pkg.f", "about": "f", "runs": runs,
            "claims": [{"id": "C1", "text": "Existing behavior is preserved.", "expect": "same", "covers": ["C1.*"]}]}
    out = {"status": "ran", "items": [item]}
    if saved is not None:
        out["broad_claims"] = saved
    return out


def test_missing_saved_gate_is_recomputed():
    pp = dr.rejudge_probes(_probes(1), product_check=True)
    assert pp["broad_claims"]["held_back"] == ["C1"]


def test_stale_saved_gate_is_replaced():
    stale = {"min_inputs": 1, "claims": ["C1"], "inputs": {"C1": 9}, "held_back": []}
    pp = dr.rejudge_probes(_probes(1, stale), product_check=True)
    assert pp["broad_claims"]["held_back"] == ["C1"] and pp["broad_claims"]["min_inputs"] == broad_claims.MIN_INPUTS


def test_saved_hold_is_not_released():
    stale = {"min_inputs": 3, "claims": ["C1"], "inputs": {"C1": 0}, "held_back": ["C1"]}
    pp = dr.rejudge_probes(_probes(broad_claims.MIN_INPUTS, stale), product_check=True)
    assert pp["broad_claims"]["held_back"] == ["C1"]


def test_enough_inputs_and_no_saved_hold_not_held_back():
    pp = dr.rejudge_probes(_probes(broad_claims.MIN_INPUTS), product_check=True)
    assert pp["broad_claims"]["held_back"] == []


def test_union_of_saved_and_recomputed_holds():
    saved = {"min_inputs": 3, "claims": ["C9"], "inputs": {"C9": 1}, "held_back": ["C9"]}
    pp = dr.rejudge_probes(_probes(1, saved), product_check=True)
    assert pp["broad_claims"]["held_back"] == ["C1", "C9"]


def test_study_route_does_not_gain_the_gate():
    pp = dr.rejudge_probes(_probes(1), product_check=False)
    assert "broad_claims" not in pp


def test_input_not_changed():
    p = _probes(1)
    orig = copy.deepcopy(p)
    dr.rejudge_probes(p, product_check=True)
    assert p == orig
