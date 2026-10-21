# A partial coverage report still applies the "never ran" cap

**Date:** 2026-10-21
**Status:** accepted

## What changed

A coverage report can leave out some changed Python files. Since the coverage-report fix, such a report counts as "not measured". On a non-product run that only lowers confidence, so a verified result stayed verified even when the report showed that a listed changed file had none of its changed executable lines run. Before that fix, the same case gave could not verify ("changed code never ran").

Now a partial report uses the same total rule as a complete report: when no changed executable line ran across all the files the report lists, the result is could not verify with the reason "changed code never ran", even if other changed files are missing from the report. If any listed file ran a changed line, the cap does not apply, so a partial report is never stricter than the complete one. This applies to product and non-product runs alike.

## Why

A missing file is a gap in the evidence. Listed files where no changed line ran at all are evidence against the result, and missing files elsewhere must not hide it. Judging each file on its own would make a partial report stricter than the complete one for the same change.

## Decision

1. A partial report where no changed line ran across all listed files gives could not verify, "changed code never ran", on any run.
2. A partial report where any listed file ran some changed lines stays "not measured": confidence is lowered on a non-product run, and a product check stays capped at could not verify.
3. Complete reports are unchanged: the "never ran" cap still applies when no changed executable line ran at all.
