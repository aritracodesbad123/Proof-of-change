# Redact paths and secrets on the runs push; skip only uncleanable files

## What changed

When a run copies its PDFs to the `runs` branch, a PDF that still contains an
internal path or a secret is no longer a reason to refuse the whole push.
The offending text is blanked or rewritten as a relative path, the PDF is
rebuilt from the cleaned text, and the cleaned copy is pushed. Only a file
that still fails the public-file check after that scrub is skipped. The skip
line names the pull-request folder and the file, for example
`widgets-7/REPORT.pdf: rewritten PDF still fails the public check`, and that
line is written into the run log and the report banner. Other PDFs and records
in the same run are still pushed.

Each pull request's `REPORT.pdf` and `record.json` are also pushed as soon as
they are written, not only at the end of the run. The GitHub token is still
never put in a remote URL, in a command, or in anything the run prints.

## Why

A single PDF that mentioned a machine-local path used to block every PDF for
that run. Runs then finished with nothing on the `runs` branch, even when most
files were fine. Separately, a run that was stopped partway never pushed the
PDFs it had already written, because the push only happened at the end.

## Decision

Scrub first, push the cleaned copy, and skip only a file that cannot be
cleaned. Name every skipped file loudly. Push each pull request's outputs as
soon as that pull request's report is written. Keep the token out of URLs and
output.

## Alternatives and tradeoffs

Refusing the whole push (the previous behaviour) kept the branch clean but
hid every good PDF behind one dirty one. Pushing the original bytes after a
warning would leak paths or secrets. Rebuilding the PDF from scrubbed text
can lose some layout detail; that is accepted so that the public branch never
holds the banned text.

## What it means for you

A run that used to show "PDFs NOT saved" because one report had a local path
will now save the cleaned reports. If a file truly cannot be cleaned, the run
log names that file and the rest still go up. Mid-run, each finished pull
request's folder appears on the `runs` branch without waiting for the whole
day to finish.

## Follow-up

When a `REPORT.pdf` cannot be cleaned, that pull request's `record.json` and
`SUMMARY.pdf` are still pushed if they clean on their own. A skip reason is
matched only by the `{pr-id}/` prefix, so one pull request never inherits
another's skip. A PDF rebuilt from cleaned text includes the line
"rebuilt from cleaned text".
