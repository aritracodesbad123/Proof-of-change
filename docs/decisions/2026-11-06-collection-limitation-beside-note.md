# A collection failure stays visible beside the already-on-base note

## What changed

When the new tests collected from a pull request were all collected again on the base and passed there, the
record still says the fix appears already present on the recorded base branch. That branch name is the one the
run stored (`master`, `2.2`, or whatever the pull request uses). It is not rewritten to main.

A different changed test file that pytest could not collect does not remove that note. The same record now
also stores a limitation sentence, `collection_limitation`, and appends it to the reason after the note. The
sentence names the files that failed to collect. The reviewer report prints that sentence in the paragraph after the note. The stored verdict comes from
the existing comparison first. ``verdict_for`` does not read the collection-failure list, so a passing
comparison is verified and a regression is needs attention. One extra cap, the same shape as the review
cap that only lowers a verified result, then applies: any verified result with an unchecked changed test
file becomes could not verify, and the reason names the file. The already-on-base note is not a condition
for that cap. Needs attention is never changed by that cap. The go/no-go is unchanged: it reads the stored
verdict, so a could-not-verify record is not an all-clear and a needs-attention record stays needs attention.

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
- Compute the verdict with the existing comparison first. A collection failure is not one of those inputs.
- If that verdict is verified and any selected changed test file failed to collect, collected no tests, or
  has a shared test the base did not execute, lower only that result to could not verify. Shared ids in a
  changed nested file are run on the base with the pull-request test body. A strengthened assertion that
  fails there stays fixed. An import of a helper that exists only on the pull request, or a missing fixture,
  is removed from fixed and from new passes and is named. A TypeError from the call under test can still be
  a fix. A test both sides collected is not a new pass when the base junit has no row. An existing file whose
  base collection saw nothing does not make every pull-request id new. A skip is not a pass. The
  already-on-base note, when the new tests really passed on the tested commit, is still attached. The commit
  is `tested_main_sha` when the run recorded it. A flagged probe still keeps needs attention; the note does
  not replace that verdict.
- If that verdict is needs attention, leave it, including when a probe flagged a difference. The limitation
  sentence is the only addition. A collection failure never turns needs attention into could not verify.
- Do not add a second go/no-go rule. The existing summary withholds "Nothing needs attention" whenever a
  stored verdict is not verified.

## Alternatives and tradeoffs

Leaving a verified result in place would let the existing go/no-go call the folder all clear while a changed
file never ran. Lowering every collection failure, including a needs-attention result, would hide that
finding. The cap copies the existing review cap in one way: it touches only a verified result. It does not
require the already-on-base note. Any verified result with an unchecked changed test file is capped. The
file that failed to collect is still named beside the note when the note is present.

Ignoring the collection list, as the report used to, would leave the failure only in the machine-readable
record. That is the gap this change closes.

## What it means for you

A check can say the fix appears already present on `master` or on `2.2`, and in the next sentence name a
changed test file pytest could not collect. If the tests that ran would have been verified, the verdict line
is could not verify. If those tests need attention, the verdict line stays needs attention. The file name is
in the report PDF. The folder summary follows that stored verdict.

A differs claim is settled only by a fixed test in a default-named edited file (`test_*.py` or
`*_test.py`) that is not a shared id. A nested file that is only in `collected_test_files`, and a shared id
the base executed, stay in `fixed` for the ordinary test verdict and do not settle the claim. No claim text
or path similarity is used as a binding. That binding does not exist yet.

A Contree side is a local checkout. The note's commit check reads that tree's git HEAD. The remote commit
the run was asked to test can be a different sha. When those two disagree the note is left off. Leaving the
note off is not evidence that the tests ran at the remote sha.

## Offline proof

`tests/test_relaxed_class_cross_run.py` shows the default inputs: a passing comparison is verified even
after `collection_failed` is added, because `verdict_for` does not read that list. The cap then lowers only
that verified result, keeps the note, and names the file. A comparison with a regression stays needs
attention through the same cap. A nested pytest run where the new tests pass on the base and `tests/boom.py`
fails to import stores could not verify, the note, and the file name. The report PDF for a could-not-verify
record and a needs-attention record shows the note and the file beside each other. The needs-attention
report does not become could not verify. `tests/test_combined_go_no_go.py` checks that the existing summary
reads those stored verdicts and does not say nothing needs attention. No live pull request is run.
