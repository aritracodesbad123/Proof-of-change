# A collection failure stays visible beside the already-on-base note

## What changed

When the new tests collected from a pull request were all collected again on the base and passed there, the
record still says the fix appears already present on the recorded base branch. That branch name is the one the
run stored (`master`, `2.2`, or whatever the pull request uses). It is not rewritten to main.

A different changed test file that pytest could not collect does not remove that note. The same record now
also stores a limitation sentence, `collection_limitation`, and appends it to the reason after the note. The
sentence names the files that failed to collect. The reviewer report prints that sentence in the paragraph
after the note, in the plain-English summary, and in the banner. The run-level go/no-go lists the same files.
It does not say that nothing needs attention while any record has this gap. A fallback summary does not say
GO for that record. The stored verdict is the one the existing rules already computed.

## Why

The collection failure was already stored on `comparison.base_new_tests.collection_failed`. The report and
the go/no-go did not show it. A reader who saw only the already-on-base note, or an all-clear summary, could
treat the run as covering every changed test file. A file that failed to collect was not checked, and it is
not a pass.

## Decision

- Keep the already-on-base note whenever every identified new test was collected and passed on the base and
  none of those tests failed. A collection error in another file does not block the note.
- Write one plain limitation sentence that lists the files pytest could not collect. Put it on the record,
  after the note in the reason, and in the report beside the note.
- Leave the stored verdict as the existing rules compute it. Do not turn the note into a pass, and do not
  turn the collection gap into could not verify. A needs-attention result stays needs attention. A verified
  result stays verified.
- Withhold the all-clear sentence ("Nothing needs attention") when any record has this gap, including a
  verified one. The counts still say how many records are verified. The gap is named in the summary.
- In the per-PR report, a verified record with this gap is "approve with notes". The banner names the files.
  It does not use the sentence that says every test behaved the same or better.

## Alternatives and tradeoffs

Rewriting a verified result to could not verify would make the go/no-go withhold its all-clear with no extra
rule. It would also hide the comparison of the tests that did run, and it would rewrite a needs-attention
finding if applied more broadly. The limitation is a gap in what was collected, not a new verdict. Showing
it beside the note, and refusing the all-clear sentence, keeps both facts visible.

Ignoring the collection list, as the report used to, would leave the failure only in the machine-readable
record. That is the gap this change closes.

## What it means for you

A check can say the fix appears already present on `master` or on `2.2`, and in the next sentence name a
changed test file pytest could not collect. The verdict line is unchanged. The folder summary does not call
that run an all-clear. The file name is in the report PDF.

## Offline proof

`tests/test_relaxed_class_cross_run.py` collects a nested test with pytest and a second file that fails to
import. When the new tests pass on the base, the note is present, `tests/boom.py` is named in the limitation
and the reason, and the verdict is the one `verdict_for` returned. A second test builds the report and the
PDF for a verified record and a needs-attention record whose base refs are `2.2` and `master`. The note and
the failed file name are in the report text and the PDF, next to each other. The stored verdict is unchanged.
The go/no-go text does not say nothing needs attention, and the fallback summary does not say GO.
`tests/test_combined_go_no_go.py` checks the same guard on a folder summary. No live pull request is run.
