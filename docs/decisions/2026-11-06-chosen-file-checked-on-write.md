# Check the chosen-PRs file when it is written

## What changed

A chosen-PRs file is the note that names which pull requests the daily run will check. The daily run
reads it with one parser, `parse_chosen` in `ops/daily_run.py`. That parser is unchanged.

A new writer, `ops/chosen_write.py`, uses that same parser at the moment the note is written. The
note is stored only when the parse still names the selection that was asked for: the same repository,
pull request number, and any head commit, base commit, install line, or test command that the
selection includes. The bytes of the note are stored as they were given. The parse is also stored
beside the note as JSON (`<file>.selection.json`). That JSON is the parser's result, not a second
rendering of the note.

When the parse drops a section, or disagrees with the selection, the writer refuses. The previous
note stays in place. The refusal is a non-zero exit, a line on the standard error stream, a line in
`<file>.preflight.log`, and a marker `<file>.write-failed.json`. The marker holds the reason and the
parse the reader actually returned, so the writer can correct the heading and try again.

The daily run, before it selects any pull request, reads that marker. If the marker is there it stops
with the same reason, writes it into the run log, and leaves through the existing no-go path (a
no-go summary PDF, then the same publish step as any other early stop). If the marker is absent, the
run's previous rule is unchanged: a file that is present but names no pull request still stops, and a
file the parser accepts is used as before. Verdict rules are not part of this change.

## Why

The note is written before the daily run. A heading the parser does not accept used to be discovered
only when the run started, and a parse that kept some pull requests and dropped one could be treated
as the selection. The dropped pull request was no longer the one that had been chosen. The failure
has to be visible when the note is written, and a run must not start as if that write had succeeded.

## Decision

- Keep one parser. The writer and the checker both call `parse_chosen`. They do not add a second grammar.
- Do not rewrite the note into a cleaned form. Either the given text parses to the selection, or it is refused.
- Compare only fields the selection includes. A heading form the parser already accepts (`owner/name #N`,
  `owner/name PR #N`, `owner/name pull request #N`, a `**Open PR:**` line, or a `###` sub-heading) is
  accepted when it produces those fields. An expected-verdict line is not part of the comparison.
- A numbered section the parser splits off and then drops is a failure even when other sections survive.
  That is the cleaned-parse case. A number that appears only in a URL is not a pull request number, which
  is the parser's existing rule.
- Record a failed or unfinished write in `<file>.write-failed.json` before the daily run. The run stops
  on that marker. A later write that the parser accepts removes the marker.
- The preflight log stamp can be set with `--now` so a simulated run can record a fixed time. That
  simulation does not produce a product verdict.

## Alternatives and tradeoffs

Re-rendering every note into one heading form would make the file easy to parse and would change notes
that the parser already accepts. Refusing at write time keeps those notes and rejects only a mismatch.

Checking the note only inside the daily run would still be after the note was written. The marker is
what the run looks at, and the writer is what creates it.

Putting the selection only in JSON, and stopping reading the note, would ignore the note the run
already uses. The note stays the input. The JSON is the parse of that note.

## What it means for you

Write the note with `python -m ops.chosen_write write <file> --intended <selection.json> --from-file <note.md>`.
The command prints the parse as JSON. A refusal names the section or field to fix and does not replace
`<file>`. Check an existing note with `python -m ops.chosen_write check <file>`. A saved selection beside
the file is used when you do not pass `--intended`.

If a write fails or stops halfway, the next daily run stops before selection and says why. Fix the note
and write it again. The run then reads the note as it did before.
