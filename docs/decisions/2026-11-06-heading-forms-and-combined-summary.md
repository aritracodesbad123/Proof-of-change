# Heading forms, and a go/no-go built from every record in the folder

## What changed

The reader for the chosen-PRs file (the note that names which pull requests to check) now accepts three
heading forms for the same pull request: `owner/name #N`, `owner/name PR #N`, and `owner/name pull request #N`.
The head SHA and the base SHA are both taken from that same section. The run then compares the pull request
against the base named there. Invoke pull request 1097 is compared with its 2.2 base, not with main.

The run-level go/no-go (`SUMMARY.md` and `SUMMARY.pdf`) is rebuilt from every `record.json` stored under a
date-and-commit folder. A later run that checks only one pull request cannot replace a summary that already
covers the other records in that folder. A summary is refused when it says "Nothing needs attention" while any
record is could not verify or needs attention.

## Why

A heading written as `owner/name PR #N` was not read, so the base SHA in that section was ignored and the
check used the pull request's current base on GitHub. A one-pull-request run could also overwrite the folder
summary. The replacement could read as an all-clear while other records in the same folder were could not
verify.

## Decision

- Read all three heading forms. Take the head SHA and the base SHA from the same section, and use that base
  when it is present.
- When a push writes a run-level summary, rebuild it from every record in the date-and-commit folder if the
  folder already holds a record this push did not write, or if the summary on the branch is a false all-clear.
- Never write "Nothing needs attention" unless every record is verified. A record with no verdict counts as
  could not verify.

## Alternatives and tradeoffs

Keeping each run's own summary is simpler, and it hides earlier results that share the folder. Rebuilding from
every record rewrites the two summary files and keeps the folder honest. Refusing a false all-clear stops a
bad summary instead of publishing it.

## What it means for you

A chosen-PRs note can name a pull request as `owner/name #N`, `owner/name PR #N`, or `owner/name pull request
#N`, and can pin the base SHA in that section. The go/no-go for a date and commit lists every stored report.
It says nothing needs attention only when every report is verified.

## Offline proof

`tests/fixtures/chosen/chosen-2026-11-04.md`, `chosen-2026-11-05.md`, and `chosen-2026-11-06.md` are real
heading notes from those days. `tests/test_chosen_heading_forms.py` checks those notes and the three heading
forms. `tests/test_combined_go_no_go.py` checks three one-pull-request runs written into one folder, and the
guard against a false all-clear.
