# The PDF is always written: no-Chrome fallback and crashed checks

Status: proposed

## What changed

The daily reports no longer drop every PDF when Chrome is missing; the built-in PDF maker writes the per-PR report
and the go/no-go summary. A check that crashes or times out partway now gets a could_not_verify record that names
the error, so it has its own PDF and a row in the summary.

## Why

A PDF of the test results and the final go/no-go verdict must always be generated, even when a check times out or
crashes. Before this change a run without Chrome wrote no PDF at all, and a crashed check had no record, no PDF and
no summary row; it appeared only in the run log.

## Decision

Rely on the existing PDF fallback (Chrome first, then the built-in maker) in the daily path too. Turn a harness
error into a could_not_verify record with the reason, and do not mark that pull request as seen, so the next run
tests it again.

## Alternatives and tradeoffs

Skipping the PDF and printing a note (the old behaviour) breaks the rule. Retrying a crashed check inside the same
run costs time and credits and may crash again. The built-in PDF is plainer than Chrome's.

## What it means for you

Every run folder's reports now include REPORT.pdf for each PR and SUMMARY.pdf, with or without Chrome. A crashed
check shows as COULD NOT VERIFY with the error, and it is tested again next run. Nothing is emailed or sent.
