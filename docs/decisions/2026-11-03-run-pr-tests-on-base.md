# Run the pull request's tests on the base tree

## What changed

The daily run now runs the test files a pull request adds or edits on the base (the old code) as well as on the
pull request (the new code). The files that run are the pull request's own text. On the base they run in the
same sandbox and with the same environment as the base run. On the pull request they run only when that file
was not already part of the test run.

A test that fails on the base and passes on the pull request is stored in the run record, in the comparison's
fixed list. That is the list the narrow cross-run rule reads. A test that cannot be collected, or that fails
while importing, is not stored as a failure and not stored as a pass, so it is not a cross-run.

The verdict rules are unchanged.

## Why

The narrow cross-run rule can settle a claim that says behaviour changes, but only when a test the pull request
added or edited fails on the base and passes on the pull request. Before this change the rule settled 0 records
in real runs. The run dated 2026-11-03 had 37 records, and the rule found 0 tests in every one of them. The run
never executed the pull request's new or edited test files on the base, so it never stored that result. A new
test that only passed on the pull request was recorded as absent on the base, which the rule does not count.

## Decision

- For each pull request, take the test files the diff adds or edits. A test file is named the way pytest's
  default `python_files` patterns name one (`test_*.py` or `*_test.py`), the same rule the cross-run already
  uses. The pytest command does not replace the project's own `python_files` setting.
- Run those files, as the pull request wrote them, against the base source, in the base side's sandbox and
  environment. Each file is its own pytest start, so a collection error in one file cannot hide a real failure
  in another. The startup-plugin retry on a Contree run is the same retry the other pytest starts use.
- Run the same files on the pull request when that file was not already a target there.
- Keep a test only when it failed on the base for a real test failure and passed on the pull request. That
  pair is what the comparison calls fixed, which is what the cross-run rule reads.
- A collection error, or an import error, on the base is dropped. A missing helper that the new tests added is
  that case. It is not a cross-run, and it is not recorded as a pass.
- Nothing in this run names a repository or a pull request. The verdict rules are not changed.

## Alternatives and tradeoffs

- Counting a new test that was never run on the base would treat "absent, then passed" as evidence. That test
  did not fail on the old code. The rule already refuses that, and this change does not weaken it.
- Treating an import error on the base as a failure would mark a test as a cross-run when the only problem was
  a helper the pull request added for its tests. Treating that error as a pass would say the old code already
  did what the new test asks. Neither is right, so the error is left out.
- Copying the pull request's new helpers onto the base as well would hide that import error and might let the
  test pass for a reason that is not the old code. Only the test files themselves are copied over.

## What it means for you

A check whose new or changed tests fail on the old code and pass on the new code now stores that pair, and the
narrow cross-run rule can see it. A test that does not import on the base does not count. A check that already
had a same claim that was seen to change, or a behaviour change no claim covers, stays not verified. That is
the same rule as before.

## Offline proof

`tests/test_cross_run_on_base.py` builds a fake pull request and runs it with the daily-run pytest command. The
new test fails on the base and passes on the pull request, the record stores that pair, and the cross-run rule
sees it. A second new test that fails to import on the base is not stored as a failure or as a pass. The
fixtures modelled on dask pull request 12645 and rich pull request 4147 still stay not verified. Nothing from
those pull requests is run again, and no live check is run.
