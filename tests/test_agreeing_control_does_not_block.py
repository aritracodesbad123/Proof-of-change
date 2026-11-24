"""A claim's own agreeing control must not block a claim other evidence already proved.

The agreeing result stays advisory. It still stops a claim that nothing else proved from becoming verified.
"""
from ops.daily_run import compare_sides, verdict_for
from poc import probes

FILES = {"all": ["pkg/widget.py", "tests/test_widget.py"]}
COVERAGE = {"status": "measured", "changed_lines_total": 2, "changed_lines_covered": 2}
DIFFERS = [{"id": "C3", "text": "the new case changes", "covers": ["c3.*"], "expect": "differs"}]


def _comparison():
    main = {"tests/test_widget.py::test_fix": ("failed", "AssertionError"),
            "tests/test_widget.py::test_keep": ("passed", "")}
    pr = {"tests/test_widget.py::test_fix": ("passed", ""),
          "tests/test_widget.py::test_keep": ("passed", "")}
    return compare_sides({"main": [main] * 3, "pr": [pr] * 3})


def _probe(main, pr, claims=None):
    spec = {"id": "model-p1", "target": "o/r#1", "about": "x", "claims": claims or DIFFERS, "source": "model"}
    item = probes.entry(spec, {"main": [main] * 3, "pr": [pr] * 3}, {"main": ["m"], "pr": ["p"]}, [], "model", None)
    item["probe_changed_line_coverage"] = {"status": "measured", "changed_lines_covered": 1,
                                           "changed_lines_total": 1, "adequacy": "adequate"}
    return {"status": "ran", "items": [item]}


def test_an_agreeing_control_on_another_input_does_not_block_a_proven_claim():
    pp = _probe({"c3.shown.result": "old", "c3.control.result": "held"},
                {"c3.shown.result": "new", "c3.control.result": "held"})
    v, reason, fl = verdict_for(_comparison(), None, None, FILES, pp, coverage=COVERAGE)
    by_name = {o["name"]: o for o in pp["items"][0]["observations"]}
    assert by_name["c3.shown.result"]["label"] == "proven" and by_name["c3.shown.result"]["state"] == "differs"
    assert by_name["c3.control.result"]["linked_by"] == "tests_prove"
    assert by_name["c3.control.result"]["advisory"] is True
    assert v == "verified"
    assert "tests_prove_not_verified" not in fl
    assert "may not reach the changed code" in reason
    assert "does not differ although the claim says it does" not in reason


def test_an_agreeing_probe_with_no_other_proof_does_not_verify():
    # One observation agrees and another is noise, so the cross-run cannot settle the claim, and nothing proved it.
    spec = {"id": "model-p1", "target": "o/r#1", "about": "x", "claims": DIFFERS, "source": "model"}
    mains = [{"c3.control.result": "old", "c3.other.result": n} for n in (1, 2, 1)]
    prs = [{"c3.control.result": "old", "c3.other.result": 1} for _ in range(3)]
    item = probes.entry(spec, {"main": mains, "pr": prs}, {"main": ["m"], "pr": ["p"]}, [], "model", None)
    item["probe_changed_line_coverage"] = {"status": "measured", "changed_lines_covered": 1,
                                           "changed_lines_total": 1, "adequacy": "adequate"}
    pp = {"status": "ran", "items": [item]}
    v, reason, fl = verdict_for(_comparison(), None, None, FILES, pp, coverage=COVERAGE)
    by_name = {o["name"]: o for o in item["observations"]}
    assert by_name["c3.control.result"]["linked_by"] == "tests_prove"
    assert by_name["c3.other.result"]["label"] == "flaky"
    assert v == "could_not_verify"
    assert "tests_prove_not_verified" in fl
    assert "does not verify the pull request" in reason


def test_a_real_difference_against_a_same_claim_still_needs_attention():
    claims = DIFFERS + [{"id": "C1", "text": "the cached value stays", "covers": ["c1.*"], "expect": "same"}]
    pp = _probe({"c3.shown.result": "old", "c1.cached": "stale"},
                {"c3.shown.result": "new", "c1.cached": "fresh"}, claims)
    v, reason, _fl = verdict_for(_comparison(), None, None, FILES, pp, coverage=COVERAGE)
    assert v == "needs_attention"
    assert "c1.cached" in reason and "differs although the claim says it does not" in reason
