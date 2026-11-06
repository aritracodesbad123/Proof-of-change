# Nested tests on the base, and a fix already present there

## What changed

The cross-run now finds tests that live in nested classes, including in a file that is not named `test_*.py` or
`*_test.py`. A cross-run is the check that runs a pull request's new or edited tests on the base (the code
before the change) as well as on the pull request. Pytest is asked to list the tests in each changed file, on
the pull request and on the base, and the node ids that appear only on the pull request are the ones that run.
A node id is pytest's own name for one test, parameters included. The list is pytest's collection output. A
file that fails to collect is not recorded as a pass.

When every one of those new tests was collected and passed on the base, and none of them failed, the run record
and the PDF say `fix appears already present on main`. If the pull request's base branch is not named main, the
same sentence uses that branch's name (`fix appears already present on master`, for example). The verdict is
not changed.

## Why

A pull request can add tests inside nested classes whose names do not start with `Test`, in a file pytest only
collects because of the project's own settings or a collection plugin. Those tests ran on the pull request and
never on the base, so the cross-run had no pair to show, even though the new tests were known.

A different check can find that the new tests already pass on the base: the failure they describe does not
happen there. The record should say that in plain words. It should not say it because some other test passed,
or because a file was never collected.

## Decision

- Take changed Python files that are not already the default `test_*.py` / `*_test.py` names: a file the
  project's `python_files` setting would collect, or any changed `.py` inside a test directory that is not a
  helper, a conftest, or a package init.
- Run `pytest --collect-only` on each such file, first on the pull request and then on the base, before the
  pull request's test file is copied onto the base. The new tests are the node ids pytest printed for the pull
  request and did not print for the base.
- Run those node ids on the base, in the base environment, with the pull request's test file copied over for
  that run and removed afterwards. Run them on the pull request as well when that side's test run did not
  already collect them.
- Keep the existing whole-file run for `test_*.py` and `*_test.py`. A failure still counts only when it is an
  assertion, or an exception raised in non-test code the diff changed. A missing helper is still neither a
  failure nor a pass.
- A collection error, a timeout, or a node id the base run does not collect is not a pass.
- Add the already-on-base sentence only when the new node ids and the ones that passed on the base are the same
  set, none of those tests failed, and none were missing. One unrelated passing test is not that set. The
  verdict rules are unchanged, so a needs-attention result stays needs attention.

## Alternatives and tradeoffs

Naming classes or decorators for one library would miss the next repository, and it would miss a parameter id
pytest spells differently. Reading pytest's collection output avoids that. Copying the test file onto the base
before collecting would hide which tests are new. Treating a test that was never collected as a pass would say
the old code already did what the new test asks, which was not shown.

Changing the verdict because the tests pass on the base would hide a real needs-attention finding. The sentence
is only a note.

## What it means for you

A check whose new nested tests fail on the base and pass on the pull request now stores that pair, and the
cross-run can see it. A check whose new tests already pass on the base says `fix appears already present on
main` (or the base branch's name) in the record and the PDF. The verdict is whatever the existing rules say.

## Offline proof

`tests/test_relaxed_class_cross_run.py` builds a small project whose new tests sit in a nested class. One test
is parametrized on the method and one on the class. Pytest's collection log is the evidence: the new node ids
are the ones pytest printed, they are absent from the base collection, and the base run's JUnit file shows they
failed there and the cross-run lists them. A second run, where the base already returns the value the new tests
expect, shows those same ids passed on the base, the failure was not reproduced, and the sentence is in the
record and in the PDF text. The verdict is the one the existing rules return. A file that fails to import is
recorded as a collection failure and is not a pass. Nothing from a live pull request is run.
