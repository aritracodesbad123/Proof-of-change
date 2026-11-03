# Chosen-PR headings, and the same exception is never proof

## What changed

The reader for the chosen-PRs file (the note that names which pull requests to check) now understands a heading
`## 1. owner/name #123`. It still understands a `**Open PR:** #123` line, and `###` sub-headings. When that file
is present but names no pull request, the run stops and says so. It does not go looking for other open pull
requests. When a library ends the run with no pull request, the report states why in one sentence.

Before two probe outputs are compared, folder names that only say which side they belong to are replaced with one
token. Those folders are side-main and side-pr, and the same pair for venv, cwd, home and out. If both sides then
show the same exception, the probe is broken: it is advisory, the check is could not verify when that is all the
probe evidence, and it is never proof of a claim.

## Why

A chosen-PRs file used headings of the form `## 1. owner/name #123`, with no github.com link and no `**Open PR:**`
line. The reader only looked for those, so it read no pull requests and searched open ones instead. Libraries the
file had named then finished with no pull request, and the report did not say why.

A probe that crashed the same way on both sides of invoke pull request 1097 was scored as a difference, and that
difference was treated as proof. The only change in the text was the side's folder name in the traceback. The
probe had not reached the behaviour the claim is about.

## Decision

- Read `owner/name` and `#123` from the heading when they are written there. A `###` heading or a `**Open PR:** #N`
  line still wins when the section has one, so the same number is not counted twice.
- If the chosen-PRs file exists and the reader finds no pull request, stop before any library is selected. A
  missing file is unchanged: the run may still look for open pull requests.
- For every library that finishes with no pull request, write one plain sentence in the run report (and keep it
  in the selection file, so a rebuilt report still has it).
- When comparing probe output, replace those side folder names first. If both sides are the same exception after
  that, mark the observation probe-broken. A message that still differs, such as the command-line name versus the
  Python name on that invoke pull request, stays a real difference and can still prove a claim. A normal result
  that only differs by a side folder name can still show that the two sides agree.

## Alternatives and tradeoffs

- Searching for open pull requests when the file is empty is what hid an unread file. Stopping is louder and
  checks nothing that day until the file names a pull request.
- Treating every shared exception type as broken, even when the message still differs, would hide a real change
  in the message. Only a message that matches after the folder names are removed is a broken probe.
- Leaving the folder names in the comparison is what counted the crash as proof.

## What it means for you

A chosen-PRs file can name a pull request as `## 1. owner/name #123`, or keep `**Open PR:** #123` under a
repository line. A file that is present but names nothing stops the run, with the reason in the report and on
the error output. A library with no pull request is listed with a sentence that says why. A probe that raises
the same exception on both sides, once side folder names are ignored, cannot verify a claim.

## Offline proof

`tests/fixtures/chosen/heading.md` is the heading form, including a section that uses `**Open PR:** #N` and a
repository on the heading. `tests/test_chosen_heading.py` checks that those pull requests are read, that an empty
file stops instead of searching, and that a library with no pull request is named in the report.

`tests/fixtures/identical_exceptions/invoke_1097.json` is the two-sided ParseError from that invoke pull request:
the same text, with side-main on one side and side-pr on the other. `tests/test_identical_exceptions.py` checks
that this is probe-broken and could not verify, that changing `param_1` to `param-1` is still a difference, and
that a normal result which only differs by a side folder can still show agreement. Nothing from the pull request
is run again.
