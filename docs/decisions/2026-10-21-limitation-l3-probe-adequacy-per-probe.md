# Known limitation L3: probe adequacy is counted per probe, not per claim file

**Date:** 2026-10-21
**Status:** accepted (known limitation)

## What changed

Nothing in the code. This entry records a known limitation, called L3, found in team review.

## Why

A probe is a short script the check writes to test one claim a pull request makes. Probe adequacy is the measure of whether the probes did enough to test the change, for example how much of the changed code they actually ran. Today that measure is counted for each probe on its own, not for each claim file (the set of claims for one pull request taken together).

So one strong probe can look adequate even when other claims in the same pull request were tested weakly, and the summary does not show adequacy for the pull request's claims as a whole.

## Decision

Keep counting adequacy per probe for now and name this as a known limitation in the docs and the paper. Counting it per claim file is future work.

## Alternatives and tradeoffs

- Change the count to per claim file now. That changes how results are measured late in the project, and we would need to re-check earlier results against the new count.
- Leave it unmentioned. That could make adequacy figures look stronger than they are.

## What it means for you

Read an adequacy figure as "this probe ran enough", not as "every claim in this pull request was tested enough". Check each claim's own result in the report.
