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

## How changed lines are counted
- Measurement is on main only. Each probe runs on the main checkpoint, and changed lines are counted in main's
  line numbers: the main lines the pull request replaces or deletes. This is the same rule local checks already use.
- A pure insertion has no line on main, so it is judged by the main lines just before and after it. A probe that
  reaches that spot counts as reaching the change.
- A probe counts as measured when the report shows at least some of the changed files. Files that do not appear
  in the report count as not run; they are not a reason to drop the measurement.

## What does not change
- Verdict rules and caps are unchanged. A probe only counts when it really ran a changed line.
- Any failure keeps the cap: no session, a run error, no report file, a short piece, a checksum mismatch, a
  report that cannot be decoded or parsed, an empty report, a probe spec that cannot be read, or a report or log that cannot be saved all leave the probe "unmeasured".
- Study runs keep the old behaviour exactly.
- No pull-request code runs outside Contree.
