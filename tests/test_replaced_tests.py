"""A test the PR removes from a test file it edits, while adding new passing tests, is a replacement, not a finding.

It never becomes verified (the old test did not run on the PR), and anything regressing still needs attention.
Synthetic fixtures only.
"""
from ops import daily_run
from ops.daily_run import compare_sides, replaced_tests

_verdict_of = daily_run.tests_verdict

FILES = {"all": ["pkg/mod.py", "tests/test_mod.py"]}


def _cmp(main, pr):
    return compare_sides({"main": [main] * 3, "pr": [pr] * 3})


def test_renamed_test_in_an_edited_test_file_is_could_not_verify_not_attention():
    cmp = _cmp({"test_mod::test_old": ("passed", ""), "test_mod::k": ("passed", "")},
               {"test_mod::test_new[a]": ("passed", ""), "test_mod::test_new[b]": ("passed", ""),
                "test_mod::k": ("passed", "")})
    assert replaced_tests(cmp, FILES) == ["test_mod::test_old"]
    v, reason, _ = _verdict_of(cmp, None, None, FILES)
    assert v == "could_not_verify"
    assert "replaced" in reason


def test_removed_test_in_a_file_the_pr_does_not_edit_still_needs_attention():
    cmp = _cmp({"test_other::test_old": ("passed", ""), "test_mod::k": ("passed", "")},
               {"test_mod::test_new": ("passed", ""), "test_mod::k": ("passed", "")})
    assert replaced_tests(cmp, FILES) == []
    assert _verdict_of(cmp, None, None, FILES)[0] == "needs_attention"


def test_removed_test_without_enough_new_passing_tests_still_needs_attention():
    cmp = _cmp({"test_mod::a": ("passed", ""), "test_mod::b": ("passed", ""), "test_mod::k": ("passed", "")},
               {"test_mod::c": ("passed", ""), "test_mod::k": ("passed", "")})
    assert replaced_tests(cmp, FILES) == []
    assert _verdict_of(cmp, None, None, FILES)[0] == "needs_attention"


def test_a_regression_keeps_every_removed_test_a_finding():
    cmp = _cmp({"test_mod::test_old": ("passed", ""), "test_mod::k": ("passed", "")},
               {"test_mod::test_new": ("passed", ""), "test_mod::k": ("failed", "boom")})
    assert replaced_tests(cmp, FILES) == []
    assert _verdict_of(cmp, None, None, FILES)[0] == "needs_attention"


def test_path_style_ids_match_the_edited_file():
    cmp = _cmp({"tests/test_mod.py::T::test_old": ("passed", ""), "tests/test_mod.py::k": ("passed", "")},
               {"tests/test_mod.py::T::test_new": ("passed", ""), "tests/test_mod.py::k": ("passed", "")})
    assert replaced_tests(cmp, FILES) == ["tests/test_mod.py::T::test_old"]
