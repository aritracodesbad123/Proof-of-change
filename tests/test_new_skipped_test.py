"""A brand-new test that skips on the PR is listed, not a finding (2026-10-14 decision)."""
from ops import daily_run


def _runs(d):
    return [dict(d) for _ in range(3)]


def test_new_skipped_test_is_listed_not_flagged():
    main = {"m.t::a": ("passed", "")}
    pr = {"m.t::a": ("passed", ""), "m.t::b[complex]": ("skipped", "complex input cannot be cast to a real dtype"),
          "m.t::b[float]": ("passed", "")}
    cmp = daily_run.compare_sides({"main": _runs(main), "pr": _runs(pr)})
    assert cmp["new_tests_skipped"] == ["m.t::b[complex]"] and cmp["other_changes"] == []
    v, reason, _ = daily_run.tests_verdict(cmp, None)
    assert v == "verified" and "1 new test(s) skipped" in reason


def test_skip_of_an_existing_test_still_counts():
    main = {"m.t::a": ("passed", ""), "m.t::c": ("passed", "")}
    pr = {"m.t::a": ("skipped", "some reason"), "m.t::c": ("passed", "")}
    cmp = daily_run.compare_sides({"main": _runs(main), "pr": _runs(pr)})
    assert cmp["new_tests_skipped"] == [] and cmp["other_changes"]
    assert daily_run.tests_verdict(cmp, None)[0] == "needs_attention"


def test_new_test_skipped_for_missing_module_stays_blocked():
    main = {"m.t::a": ("passed", "")}
    pr = {"m.t::a": ("passed", ""), "m.t::n": ("skipped", "could not import 'duckdb'")}
    cmp = daily_run.compare_sides({"main": _runs(main), "pr": _runs(pr)})
    assert cmp["new_tests_skipped"] == [] and cmp["skipped_missing_dependency"]
