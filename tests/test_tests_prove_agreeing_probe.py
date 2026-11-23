"""An agreeing probe result is advisory when the tests already prove the change.

The tests prove it when a test in an edited test file fails on the base and passes on the pull request, every
changed line is covered, and nothing regressed. Without that proof the same result still needs attention.
A real difference is not this case.
"""
from ops.daily_run import compare_sides, verdict_for
from poc import probes
from reports.pr_report import probes_section
from reports.reviewer import Report, to_md

FILES = {"all": ["pkg/widget.py", "tests/test_widget.py"]}
COVERAGE = {"status": "measured", "changed_lines_total": 2, "changed_lines_covered": 2}
DIFFERS = [{"id": "C3", "text": "the new case changes", "covers": ["c3.*"], "expect": "differs"}]


def _fixed_comparison():
    main = {"tests/test_widget.py::test_fix": ("failed", "AssertionError"),
            "tests/test_widget.py::test_keep": ("passed", "")}
    pr = {"tests/test_widget.py::test_fix": ("passed", ""),
          "tests/test_widget.py::test_keep": ("passed", "")}
    cmp = compare_sides({"main": [main] * 3, "pr": [pr] * 3})
    # The changed test module also fails to load, so the tests alone cannot verify the pull request.
    cmp["load_failed_both"] = ["tests.test_widget"]
    return cmp


def _probe(main, pr, claims=None):
    spec = {"id": "model-p1", "target": "o/r#1", "about": "x", "claims": claims or DIFFERS, "source": "model"}
    item = probes.entry(spec, {"main": [main] * 3, "pr": [pr] * 3}, {"main": ["m"], "pr": ["p"]}, [], "model", None)
    item["probe_changed_line_coverage"] = {"status": "measured", "changed_lines_covered": 1,
                                           "changed_lines_total": 1, "adequacy": "adequate"}
    return {"status": "ran", "items": [item]}


def test_agreeing_result_is_advisory_when_the_tests_already_prove_the_change():
    pp = _probe({"c3.regex_match_normalized": "old"}, {"c3.regex_match_normalized": "old"})
    v, reason, _ = verdict_for(_fixed_comparison(), None, None, FILES, pp, coverage=COVERAGE)
    obs = pp["items"][0]["observations"][0]
    assert obs["linked_by"] == "tests_prove"
    assert "may not reach the changed code" in obs["note"]
    assert v != "needs_attention"
    assert v != "verified"
    assert "may not reach the changed code" in reason
    assert "does not differ although the claim says it does" not in reason
    R = Report()
    probes_section(R, {"probes": pp, "baseline": "full"}, lambda name: name)
    text = to_md(R)
    assert "may not reach the changed code" in text
    assert "Advisory:" in text


def test_agreeing_result_without_test_proof_still_needs_attention():
    pp = _probe({"c3.regex_match_normalized": "old"}, {"c3.regex_match_normalized": "old"})
    partial = {"status": "measured", "changed_lines_total": 2, "changed_lines_covered": 1}
    v, reason, _ = verdict_for(_fixed_comparison(), None, None, FILES, pp, coverage=partial)
    assert pp["items"][0]["observations"][0].get("linked_by") != "tests_prove"
    assert v == "needs_attention"
    assert "does not differ although the claim says it does" in reason


def test_a_real_difference_still_needs_attention_when_the_tests_prove_the_change():
    claims = DIFFERS + [{"id": "C1", "text": "the cached value stays", "covers": ["c1.*"], "expect": "same"}]
    pp = _probe({"c3.regex_match_normalized": "old", "c1.normalized": "stale"},
                {"c3.regex_match_normalized": "old", "c1.normalized": "fresh"}, claims)
    v, reason, _ = verdict_for(_fixed_comparison(), None, None, FILES, pp, coverage=COVERAGE)
    by_name = {o["name"]: o for o in pp["items"][0]["observations"]}
    assert by_name["c3.regex_match_normalized"]["linked_by"] == "tests_prove"
    assert by_name["c1.normalized"].get("linked_by") != "tests_prove"
    assert v == "needs_attention"
    assert "c1.normalized" in reason and "differs although the claim says it does not" in reason
