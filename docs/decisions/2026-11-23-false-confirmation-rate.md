# False confirmations come from the hand-check file

## What changed

The false-confirmation rate and the wrong-pass count read `data/hand_checks.jsonl` in this repository.
They do not read a label off a saved record. A missing file is reported as hand checks not available.
A malformed row stops the report.

A row applies only when the repository, the pull request number, and the head commit all match that
record. Every verified record of a pull request is checked, not only the latest. A label for one
head is not applied to a record at another head. The pull request counts once. The verdict table
still uses the latest record.

A wrong pass is a verified pull request whose matching row has `broken` set to true. The
false-confirmation rate is that count over the verified pull requests that have a matching row.
Verified pull requests with no matching row are listed as unlabelled. They are not counted as passes.
`tool_verdict` and `score` are notes and do not change the rate.

## Why

Saved records do not carry hand checks, so a rate that looked there was empty. The rows belong in
this repository so a later run can reproduce the rate without another checkout. Matching the head
commit stops an older check from labelling a newer commit of the same pull request.

## Decision

Keep the stored verdict. Do not rewrite a record. Add `data/hand_checks.jsonl` unchanged.
Count each pull request once. Leave a verified pull request with no matching row out of the
denominator and say that it is unlabelled.

## Alternatives and tradeoffs

Reading a label from the record would score nothing until those fields are filled in, and it would
mix notes from a run with the hand check. Treating a missing row as a pass would hide pull requests
nobody has checked. Using only the pull request number, without the head commit, would apply an old
check to a commit it did not cover.

## What it means for you

The benchmark table is unchanged. Under it, the hand-check lines appear when `data/hand_checks.jsonl`
is present, and the report says hand checks are not available when it is not. For a directory of
saved records, the report still lists every stored verdict, once per record and once per pull request.
