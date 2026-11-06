# Always push the run-level go/no-go summary; the saved banner follows the final push

## What changed

The run-level go/no-go `SUMMARY.pdf` and `SUMMARY.md` are now pushed into the
run folder itself (`runs/<date>/<commit>/`), not only copied into each pull
request's folder. They are never skipped. If ordinary scrubbing cannot clean
them, each line that still fails the public-file check is blanked and the PDF
is rebuilt from the cleaned text; if the PDF's text cannot be read, it is
rebuilt from `SUMMARY.md`.

Before each push, every earlier "PDFs saved", "PDFs NOT saved" and "PDFs
skipped" line is removed from the markdown reports, the run log and the local
PDFs. Only the final push result is written back. A `record.json` that cannot
be cleaned is held back and named instead of refusing the whole set.

## Why

A run's summary went missing from the `runs` branch: the first publish refused
the whole set, the second pushed only the pull-request folders, and the
success line was appended after the old "NOT saved" banner, which stayed at the
top of `SUMMARY.md`. The go/no-go summary must never be lost.

## Decision

Treat the run-level summary as must-push: redact and push, never skip. Derive
the saved / not-saved banner only from the final push result.

## Alternatives and tradeoffs

Skipping an uncleanable summary keeps the branch tidy but loses the one file
readers need most. Blanking whole lines can remove some detail; that is
accepted over losing the file. Rewriting the log drops earlier push status
lines; the final result is what matters to a reader.
