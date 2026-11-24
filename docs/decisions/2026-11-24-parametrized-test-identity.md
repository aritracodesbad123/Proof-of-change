# A test that gained parameter ids is the same test

## What changed

A test that was one id on the base and a parametrized id on the pull request is the same test.
`test_x` and `test_x[param]` are that pair. The parametrized id is judged by its own result. The bare id is
not listed as removed, and it is not reported as a replaced test that did not run on the pull request.

This also covers a parametrized id that failed on the base and passed on the pull request, so it was already
filed under the tests that got fixed. That id is still a fix. It is also the same test as the bare id, so the
bare id is not a second finding.

A test that was removed, with no parametrized id that actually ran, is still removed. A parametrized id that
was only skipped did not run, so it does not clear the removal. A removed test that the pull request replaced
with a different new test is still reported as a replaced test that did not run.

## Why

Turning an existing test into a parametrized one changes the id pytest reports. The bare id is absent on the
pull request, and the parametrized id can already have been recorded as a failure on the base and a pass on
the pull request. The comparison then saw a removed test, and a different new passing test in the same file
made that removal look like a replacement. The old test had run, under the new parameter id.

## Decision

Match a removed id to a parametrized id of the same test only when that parametrized id ran (passed or
failed). Record the pair as re-parametrized. Leave the parametrized id in the list its own result already
chose. Do not match a skipped id. Do not match a different test name.

The same reading is applied to a saved comparison when a verdict is derived again, so the saved file is not
rewritten.

## Alternatives and tradeoffs

Treating every removed id in an edited test file as replaced would clear a real deletion whenever the pull
request added any passing test. Ignoring the parametrized id whenever it is already in the fixed list would
keep calling the bare id removed. Requiring the parameter ids to match on both sides would miss a test that
was not parametrized before.

## What it means for you

A test that only gained parameter ids stays one test. Its pass or failure is the result that counts. A test
that is gone, or that only comes back as a skip, is still pointed out.
