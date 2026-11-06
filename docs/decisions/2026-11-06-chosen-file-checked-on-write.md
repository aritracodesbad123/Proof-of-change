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
note stays in place. The refusal is the same no-go summary a refused run already leaves:
`<file>.no-go/SUMMARY.pdf`, written by `poc/pdf_always.nogo_summary`, naming the section or field
that disagreed. The standard error stream prints that same reason
and names the PDF. A marker, `<file>.write-failed.json`, holds the reason and the parse so the note
can be corrected and written again.

The daily run reads that marker before it fetches or selects. If the marker is there it stops with
the same reason and then follows the existing early-stop path. If the marker is absent, the run's
previous rule is unchanged: a file that is present but names no pull request still stops, and a file
the parser accepts is used as before. Verdict rules are not part of this change.

## Why

The note is written before the daily run. A parse that drops a pull request, or that disagrees with
the selection, must be refused when the note is written. A non-zero exit recorded only in a log is
not the signal a refused run already uses. The signal is the no-go summary PDF.

## Decision

- Keep one parser. The writer and the checker both call `parse_chosen`. They do not add a second grammar.
- Do not rewrite the note into a cleaned form. Either the given text parses to the selection, or it is refused.
- Compare only fields the selection includes. A heading form the parser already accepts (`owner/name #N`,
  `owner/name PR #N`, `owner/name pull request #N`, a `**Open PR:**` line, or a `###` sub-heading) is
  accepted when it produces those fields. An expected-verdict line is not part of the comparison.
- A numbered section the parser splits off and then drops is a failure even when other sections survive.
  That is the cleaned-parse case. A number that appears only in a URL is not a pull request number, which
  is the parser's existing rule.
- On refusal, write `<file>.no-go/SUMMARY.pdf` with the same helper a refused run uses. Name the
  disagreement. Leave the previous note in place.
- Record the refusal in `<file>.write-failed.json`. The daily run stops on that marker before it
  fetches. A later write that the parser accepts removes the marker and the no-go PDF.

## Alternatives and tradeoffs

Re-rendering every note into one heading form would make the file easy to parse and would change notes
that the parser already accepts. Refusing at write time keeps those notes and rejects only a mismatch.

Checking the note only inside the daily run would still be after the note was written. The no-go
PDF is written at refusal time. The marker is what the run looks at if that PDF was ignored.

Putting the selection only in JSON, and stopping reading the note, would ignore the note the run
already uses. The note stays the input. The JSON is the parse of that note.

## What it means for you

Write the note with `python -m ops.chosen_write write <file> --intended <selection.json> --from-file <note.md>`.
The command prints the parse as JSON. A refusal does not replace `<file>`. It leaves
`<file>.no-go/SUMMARY.pdf`, which names the section or field to fix. Check an existing note with
`python -m ops.chosen_write check <file>`. A saved selection beside the file is used when you do not
pass `--intended`.

If a write fails or stops halfway, the next daily run stops before it fetches and says why. Fix the
note and write it again. The run then reads the note as it did before.
