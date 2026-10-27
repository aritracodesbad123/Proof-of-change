# Probe line coverage is measured inside Contree on product checks

Date: 27 Oct 2026

## Problem
In Contree-only checks every probe was stamped "probe coverage not measured" without any attempt to measure it.
The probe adequacy rule then dropped each probe's matching results, so a Contree-only check could never reach
verified, even when a probe really ran the changed code.

## Decision
On the product route, after the timed probe runs, each probe runs once more on the main checkpoint in Contree
under coverage.py, limited to the changed files. Coverage is already part of the checkpoint, so nothing extra is
installed. The report is packed to a file inside Contree and fetched in checksummed pieces, the same way the
test coverage report is fetched, then mapped to the main-side changed lines with the existing adequacy rule.

## What does not change
- Verdict rules and caps are unchanged. A probe only counts when it really ran a changed line.
- Any failure keeps the cap: no session, a run error, no report file, a short piece, a checksum mismatch, a
  report that cannot be decoded or parsed, or an empty report all leave the probe "unmeasured".
- Study runs keep the old behaviour exactly.
- No pull-request code runs outside Contree.
