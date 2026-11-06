# A new test counts only when the base actually ran it

## What changed

A pull request can add tests in a file whose name is not `test_*.py` or `*_test.py`. Those tests are
collected with each side's own interpreter. The ones that exist only on the pull request then run on the
base tree, in the base environment, and on the pull request.

A result is kept only when the base run produced a real pass, failure, or skip for that test. If the base
could not collect or load the file, or the copy onto the base failed, the record names that file and the
check cannot be verified. A test that passed only on the pull request is not counted as a new passing test,
and it is not described as a failure that the base reproduced. A skipped new test is not counted as a pass.

The note that new tests already pass names the tested base commit. It is not added from the branch name,
it is not added when a probe observation is flagged, and it does not change the verdict. Those fixed ids are
test results. They are not attached to a behaviour-claim id.

A test both sides already collect is not a new test. If the base run does not actually execute it, that file
is named and the test is not counted as a new pass. When the base collects nothing, the file is run only to
show that, and no id from that run is stored as fixed.

## Why

Collecting tests on the pull request and treating every id the base did not print as a new test marked
passing tests that the base interpreter had never run. A second changed file that failed to import
disappeared from the result, so the check could still say verified. Copying a test onto a path whose
parent was a file aborted the whole run.

## Decision

The default `test_*.py` and `*_test.py` files stay on the existing whole-file check. Other changed test
files use collection, then a run of the new ids, or of the file itself when the two collections cannot
be compared. Each side uses the dependencies its own checkout declares. The base checkout has to be the
recorded tested commit when that checkout is a git tree. Probe verdicts are unchanged: a flagged
preservation claim stays needs attention.

## Alternatives and tradeoffs

Treating an empty base collection as "every pull-request test is new" would run ids the base cannot
collect and then store the pull-request pass. That is the result this change refuses. Stopping the whole
check on the first copy error would hide a real failure in another file.

## What it means for you

A new nested test that fails on the base and passes on the pull request is stored as fixed. If the base
never executed it, or another changed test file failed to collect, the report names that file and the
result is not verified. The branch name alone is not evidence that the fix is already on the base.
