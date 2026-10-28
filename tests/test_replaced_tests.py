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


def test_an_empty_test_added_in_a_different_file_does_not_cover_a_removal():
    files = {"all": ["pkg/mod.py", "tests/test_mod.py", "tests/test_other.py"]}
    cmp = _cmp({"test_mod::test_real": ("passed", ""), "test_mod::k": ("passed", "")},
               {"test_other::test_empty": ("passed", ""), "test_mod::k": ("passed", "")})
    assert replaced_tests(cmp, files) == []
    assert _verdict_of(cmp, None, None, files)[0] == "needs_attention"


def test_a_same_named_test_file_in_another_folder_does_not_match():
    files = {"all": ["pkg/mod.py", "tests/b/test_mod.py"]}
    cmp = _cmp({"tests/a/test_mod.py::test_old": ("passed", ""), "tests/b/test_mod.py::k": ("passed", "")},
               {"tests/b/test_mod.py::test_new": ("passed", ""), "tests/b/test_mod.py::k": ("passed", "")})
    assert replaced_tests(cmp, files) == []
    dotted = _cmp({"tests.a.test_mod::test_old": ("passed", ""), "tests.b.test_mod::k": ("passed", "")},
                  {"tests.b.test_mod::test_new": ("passed", ""), "tests.b.test_mod::k": ("passed", "")})
    assert replaced_tests(dotted, files) == []
    assert _verdict_of(dotted, None, None, files)[0] == "needs_attention"


def test_a_bare_module_id_matching_two_edited_folders_matches_neither():
    files = {"all": ["tests/a/test_mod.py", "tests/b/test_mod.py"]}
    cmp = _cmp({"test_mod::test_old": ("passed", ""), "test_mod::k": ("passed", "")},
               {"test_mod::test_new": ("passed", ""), "test_mod::k": ("passed", "")})
    assert replaced_tests(cmp, files) == []


def test_editing_a_non_test_file_of_the_same_name_does_not_cover_a_removal():
    files = {"all": ["pkg/mod.py"]}
    cmp = _cmp({"mod::test_old": ("passed", ""), "mod::k": ("passed", "")},
               {"mod::test_new": ("passed", ""), "mod::k": ("passed", "")})
    assert replaced_tests(cmp, files) == []
    assert _verdict_of(cmp, None, None, files)[0] == "needs_attention"


def test_nothing_ran_on_both_sides_keeps_the_removal_a_finding():
    cmp = _cmp({"test_mod::test_old": ("passed", "")}, {"test_mod::test_new": ("passed", "")})
    assert replaced_tests(cmp, FILES) == []
    skipped = _cmp({"test_mod::test_old": ("passed", ""), "test_mod::k": ("skipped", "")},
                   {"test_mod::test_new": ("passed", ""), "test_mod::k": ("skipped", "")})
    assert replaced_tests(skipped, FILES) == []
    assert _verdict_of(skipped, None, None, FILES)[0] != "verified"


def test_saved_comparison_without_ids_keeps_the_finding():
    """A comparison saved before new_tests_passing_ids existed has no ids: no replacement is assumed."""
    cmp = _cmp({"test_mod::test_old": ("passed", ""), "test_mod::k": ("passed", "")},
               {"test_mod::test_new[a]": ("passed", ""), "test_mod::k": ("passed", "")})
    old = {k: v for k, v in cmp.items() if k != "new_tests_passing_ids"}
    assert replaced_tests(old, FILES) == []
    assert _verdict_of(old, None, None, FILES)[0] == "needs_attention"


def test_ids_are_rebuilt_from_saved_junit(tmp_path):
    def junit(path, names):
        cases = "".join(f'<testcase classname="test_mod" name="{n}"/>' for n in names)
        path.write_text(f'<testsuites><testsuite name="s" tests="{len(names)}">{cases}</testsuite></testsuites>')
    for i in (1, 2, 3):
        junit(tmp_path / f"junit-main-{i}.xml", ["test_old", "k"])
        junit(tmp_path / f"junit-pr-{i}.xml", ["test_new", "k"])
    saved = {k: v for k, v in _cmp({"test_mod::test_old": ("passed", ""), "test_mod::k": ("passed", "")},
                                    {"test_mod::test_new": ("passed", ""), "test_mod::k": ("passed", "")}).items()
             if k != "new_tests_passing_ids"}
    rec = {"comparison": saved, "runs_per_side": 3, "files": FILES, "per_run": [], "verdict": "needs_attention",
           "reason": ""}
    out = daily_run.rejudge(rec, tmp_path)
    assert out["comparison"]["new_tests_passing_ids"] and replaced_tests(out["comparison"], FILES)
