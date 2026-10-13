# Chosen-PRs file and missing-dependency test failures

## What changed

The checker that compares a pull request (a proposed code change) with the library's current code now reads the
chosen-PRs file more completely, finds test files that use a second common name, and stops treating a missing
optional module as a break caused by the pull request.

A *chosen-PRs file* is a Markdown note that lists which pull requests to check and how to run their tests. A
*verdict* is the result of a check: verified, needs attention, or could not verify. A *head SHA* is the commit id
of the exact snapshot the pull request proposes.

Four behaviours changed:

1. A library section can list more than one pull request, each under its own sub-heading such as
   `### Primary PR: #8946`. Each one is kept, with its own head SHA.
2. A test command written on a `- Test:` line is used when the file does not have the older
   `- Test (subset...):` line. If both are present, the subset line still wins. If a line names two commands, the
   first one in backticks is the command that runs.
3. Test files named `something_test.py` are recognised, not only `test_something.py`. When the change touches a
   source file, the search for a matching test also looks for `<name>_test.py`.
4. A test that exists only on the pull-request side and fails only because Python cannot import a module that is
   not installed (for example `ModuleNotFoundError: No module named 'pandas'`) is recorded as blocked by that
   missing module. The verdict is could not verify, and the reason says the comparison is incomplete because the
   module is not installed. It is not reported as a new test that the pull request broke.

The older layout, one `**Open PR:** #N` under each library heading, is unchanged.

Expected verdicts (a result written down ahead of time, used only to score the check afterwards) are still ignored
while the check runs. Only the scorer reads them, and only from the standard line inside that pull request's own
section (`Expected Proof-of-Change verdict`, followed by the verdict in backticks). A section that uses different
wording is left unscored.

## Why

Some notes were being dropped, so the check either skipped a pull request or ran with no tests:

- A library heading that listed a second pull request under a sub-heading produced no entry at all, because the
  reader looked only for `**Open PR:** #N`.
- A test command on a `- Test:` line was ignored, because the reader looked only for `- Test (subset...):`.
- Repositories that name tests `something_test.py` (the file sits under `tests/` and ends in `_test.py`) got no
  mapped tests, and the run reported that no tests could be mapped to the touched files.

Separately, a new test that failed only because an optional library was not installed was counted as a failure of
the pull request. Tests that already existed, and failed the same way on both sides, were already treated as
pre-existing. The new ones pushed the verdict to needs attention ("N new test(s) fail on the PR") even though the
pull request did not break them. The environment simply did not have the module.

## Decision

- Keep one reader for the chosen-PRs file. A library section is either the old single `**Open PR:**` entry or a
  list of `###` sub-headings that each contain a pull request number. The number is the first `#` plus digits on
  that heading, so a title that also mentions another number does not steal it.
- Read install and test commands from the pull request's own text first, then from the shared notes above the
  first sub-heading. Do not read an expected verdict in that pass.
- Score an expected verdict only from the standard line, and only from that pull request's own text.
- Treat `*_test.py` like `test_*.py` when picking touched tests and when searching by file name.
- When a new test's failure message is one the comparison already treats as a missing module, put that test in the
  existing missing-dependency list. The verdict rule for that list already says the check is not fully verified.
  Do not also count the test as a new failure.
- After the tests run, still ask the pull-request environment whether the module imports. If it does import, the
  failure goes back to the new-failure list, because the message was not caused by a missing install. When an old
  result is scored again and the environment is gone, a failure that was not confirmed at the time stays a new
  failure, so an old result is not quietly rewritten.

## Alternatives and tradeoffs

- A second file format, or a small table instead of Markdown sub-headings, would be easier to parse and harder to
  write by hand. The notes already use headings, so the reader follows that shape.
- Guessing an expected verdict from a nearby line that only says "expected verdict" and then adds a condition
  would score
  more pull requests, and would also score ones that were deliberately left conditional. Those stay unscored.
- Counting every `ModuleNotFoundError` as a missing dependency, including tests that passed on the current code
  and fail on the pull request, would hide real regressions. Only tests that are new on the pull-request side are
  treated this way.
- Adding a new comparison bucket, separate from the existing missing-dependency list, would make the report show
  "failed to import" and "skipped" apart. Both mean the same thing for the verdict (the check is incomplete), so
  they share one list. The reason says "skipped or blocked" to cover both.
- Trusting the failure message without checking that the module is absent would mis-label a real bug that happens
  to raise `ModuleNotFoundError` for a module that is installed. The environment check prevents that on a live
  run. A later rescore cannot repeat the check, so it keeps the earlier decision.

## What it means for you

- A chosen-PRs file can list several pull requests under one library. Each needs its own sub-heading with the
  pull request number and its own head SHA.
- You can write the test command on a `- Test:` line, with the pytest command in backticks. The first command
  in backticks is the one that runs. The older `- Test (subset...):` line still takes priority when you use it.
- Libraries that name tests `name_test.py` now get those files mapped.
- If new tests fail only because an optional module is not installed, the verdict is could not verify, and the
  reason names that module. Add the module to that library's `optional_test_deps` in `ops/daily_run.py` if the
  check should install it, then run the check again.
- A test that passed before and fails on the pull request is still needs attention, even when the message names
  a module.
