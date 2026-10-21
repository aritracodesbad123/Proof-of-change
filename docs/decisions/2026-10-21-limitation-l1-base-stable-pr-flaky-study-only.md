# Known limitation L1: base-stable, PR-flaky tests in the study only

**Date:** 2026-10-21
**Status:** accepted (known limitation)

## What changed

Nothing in the code. This entry records a known limitation, called L1, so the docs and the paper can point to it.

## Why

A flaky test is one that passes on some runs and fails on others without any code change. The check reruns tests to spot this. Before the fix in #69, a test that was stable on the base (the code before the pull request) but flaky only on the pull request was treated as noise and ignored. That pattern can be a real sign that the pull request broke something, so ignoring it could hide a problem.

## Decision

1. The product has the fix from #69: a test that is stable on the base but flaky on the pull request is no longer ignored.
2. The research study is frozen at tag `study-v1.1` (commit `80b97f9`), which does not include that fix. L1 applies to the study only.
3. We do not change the frozen study to add the fix. After the study runs, we will report how many of its 92 pairs are affected, with each affected verdict shown both with and without the fix. That count does not exist yet and is not claimed anywhere.

## Alternatives and tradeoffs

- Re-freeze the study with the fix included. That would change the study after its list and code were fixed in advance, which weakens it as a fair test.
- Leave the gap unmentioned. That would overstate the study's results.

The cost of our choice is that a few study verdicts may differ from what the current product would say.

## What it means for you

Product checks are not affected. When reading the study results, treat L1 as a known limitation until the affected-pair count is published.
