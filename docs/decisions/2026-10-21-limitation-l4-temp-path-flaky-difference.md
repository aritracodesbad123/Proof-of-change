# Known limitation L4: a real difference that contains a temp path is treated as flaky

**Date:** 2026-10-21
**Status:** accepted (known limitation, agreed 2026-10-20)

## What changed

Nothing in the code. This entry records a known limitation, called L4, with example case F01.

## Why

The check runs each probe on the code before and after the pull request and compares the outputs. If an output changes from run to run on the same side, it is labelled flaky and set aside as noise. A temp path (a file or folder name made up fresh on each run, for example under `/tmp/`) changes every run.

When a real before/after difference also contains a temp path, the whole difference is labelled flaky and thrown away, so a real change can be missed.

## Evidence (example F01)

F01 is pallets/click#1470, a pull request that was later reverted by click#1543, so it is labelled a regression. It was one of 8 fresh cases in a test run on 2026-10-20 that compared the check before and after a set of linking fixes.

- The probe recorded the shell command click builds. Before the pull request the output was `echo "/tmp/..."`; after it, `echo /tmp/...` without quotes. That is the real behaviour change behind the regression (a change in how the path is quoted).
- Because the temp-file name changed between runs, the difference was labelled flaky and ignored. With the earlier check this let the case come out as verified, which was a miss.
- After the linking fixes, the same case came out as needs_attention, but for a weak reason: a claim did not show the difference it said it would. The temp-path difference itself was still thrown away.

## Decision

Agreed on 2026-10-20: this will not be fixed before 1 November 2026. The paper names it as a known limitation.

## Alternatives and tradeoffs

- Strip temp paths from outputs before deciding flakiness, then compare what is left. This is the likely fix, but it touches the core comparison and needs its own tests, so it waits until after 1 November.

## What it means for you

If a pull request changes how paths or file names are printed or quoted, a needs_attention or verified result may not reflect that change. Check such cases by hand.
