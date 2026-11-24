"""A test that gained parameter ids is the same test. A test that was really removed or skipped is still flagged."""
from ops.daily_run import apply_execution_evidence_filters, compare_sides, verdict_for

FILES = {"all": ["test/test_m.py"]}
BARE = "test.test_m.C::test_x"
PARAM = "test.test_m.C::test_x[a]"
KEEP = "test.test_m.C::test_keep"
NEW = "test.test_m.C::test_new"
GONE = "test.test_m.C::test_gone"


def _runs(main, pr):
    return {"main": [main] * 3, "pr": [pr] * 3}


def test_a_test_that_became_parametrized_is_not_removed_or_replaced():
    main = {BARE: ("passed", ""), PARAM: ("failed", "AssertionError: old"), KEEP: ("passed", "")}
    pr = {PARAM: ("passed", ""), NEW: ("passed", ""), KEEP: ("passed", "")}
    cmp = compare_sides(_runs(main, pr))
    assert BARE not in cmp["removed_tests"]
    assert PARAM in cmp["fixed"]
    (entry,) = [item for item in cmp["reparametrized"] if item["test"] == "test.test_m.C::test_x"]
    assert BARE in entry["removed_ids"] and PARAM in entry["added_ids"]
    verdict, reason, _ = verdict_for(cmp, None, None, FILES)
    assert "replaced test was not run" not in reason
    assert "removed on the PR side" not in reason
    assert verdict == "verified"


def test_a_saved_comparison_is_read_the_same_way():
    cmp = {
        "same": 1, "same_skipped_both": 0, "regressions": [], "fixed": [PARAM],
        "new_tests_passing": 1, "new_tests_passing_ids": [NEW], "new_tests_failing": [],
        "new_tests_skipped": [], "removed_tests": [BARE], "reparametrized": [],
        "skipped_missing_dependency": [], "flaky": [], "pr_unstable": [], "pr_unstable_noisy": [],
        "other_changes": [], "preexisting_failures": [], "load_failed_both": [],
        "load_failed_pr": [], "load_failed_main": [], "executed": {"main": 2, "pr": 2},
    }
    apply_execution_evidence_filters(cmp)
    assert cmp["removed_tests"] == []
    verdict, reason, _ = verdict_for(cmp, None, None, FILES)
    assert verdict == "verified" and "replaced test was not run" not in reason


def test_a_genuinely_removed_test_is_still_flagged():
    main = {GONE: ("passed", ""), KEEP: ("passed", "")}
    pr = {KEEP: ("passed", ""), NEW: ("passed", "")}
    cmp = compare_sides(_runs(main, pr))
    assert cmp["removed_tests"] == [GONE] and cmp["reparametrized"] == []
    verdict, reason, _ = verdict_for(cmp, None, None, FILES)
    assert verdict == "could_not_verify" and "replaced test was not run" in reason


def test_a_skipped_parametrized_id_does_not_clear_a_removal():
    main = {BARE: ("passed", ""), KEEP: ("passed", "")}
    pr = {PARAM: ("skipped", "skip: later"), KEEP: ("passed", "")}
    cmp = compare_sides(_runs(main, pr))
    assert cmp["removed_tests"] == [BARE]
    assert PARAM in cmp["new_tests_skipped"]
    verdict, reason, _ = verdict_for(cmp, None, None, FILES)
    assert verdict == "needs_attention"
    assert "removed on the PR side" in reason


def test_an_unparametrized_id_that_only_gained_parameters_is_reparametrized():
    main = {BARE: ("passed", ""), KEEP: ("passed", "")}
    pr = {PARAM: ("passed", ""), KEEP: ("passed", "")}
    cmp = compare_sides(_runs(main, pr))
    assert cmp["removed_tests"] == []
    assert cmp["reparametrized"][0]["test"] == "test.test_m.C::test_x"
    verdict, reason, _ = verdict_for(cmp, None, None, FILES)
    assert verdict == "verified" and "re-parametrized" in reason
