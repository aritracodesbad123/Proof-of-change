# Flaky project tests are shown but do not decide the verdict

## What changed

The project's own tests run three times on each side. If a test gives different results between runs on the
*same* side (for example it passes, then skips because the machine was short on memory, then passes again), it is
"flaky". Before, a flaky test on its own turned a clean result into "could not verify". Now it is still listed in
the reason, but it no longer decides the verdict. This is the same noise rule we already use for probe results.

A real difference still counts: a test that passes on one side and fails on the other every time is a
regression, whether or not some other test is flaky.

## Why

A result that changes between runs on one side says something about the machine, not about the pull request. A
documentation-only change was reported as a problem only because a memory-hungry test skipped itself on some runs.
This is the general cause, so the rule is general; nothing is special-cased for one pull request.

## Trade-offs

- A real problem that shows up only sometimes, and on one side only, could now be missed by the tests. The
  flaky test is still named in the reason, so a reader can see it.
- The documentation comment for the probe step also said a flaky result meant "needs attention"; it now matches
  the rule.
- A test was added for the install overrides option (an optional file that leaves out an add-on that cannot be
  built on this machine), which had none.
