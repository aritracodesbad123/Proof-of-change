# A partial coverage report still applies the "never ran" cap

**Date:** 2026-10-21
**Status:** proposed

## What changed

A coverage report can leave out some changed Python files. Since the coverage-report fix, such a report counts as "not measured". On a non-product run that only lowers confidence, so a verified result stayed verified even when the report showed that a listed changed file had none of its changed executable lines run. Before that fix, the same case gave could not verify ("changed code never ran").

Now, whenever a report lists a changed file with at least one changed executable line and none of those lines ran, the result is could not verify with the reason "changed code never ran", even if other changed files are missing from the report. This applies to product and non-product runs alike.

## Why

A missing file is a gap in the evidence. A listed file whose changed lines never ran is evidence against the result. Missing files elsewhere must not hide it.

## Decision

1. A partial report with a listed changed file at 0 changed lines run gives could not verify, "changed code never ran", on any run.
2. A partial report where every listed file ran some changed lines stays "not measured": confidence is lowered on a non-product run, and a product check stays capped at could not verify.
3. Complete reports are unchanged: the "never ran" cap still applies when no changed executable line ran at all.
