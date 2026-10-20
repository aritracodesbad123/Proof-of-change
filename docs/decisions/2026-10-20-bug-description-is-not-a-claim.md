# A description of the old bug is not an unchanged claim

## What changed

A sentence that describes the bug being fixed, or the old behaviour, is not treated as a claim that results stay the same.

## Why

A pull request often says what used to go wrong, including that the old code left something unchanged. Reading that as a promise that results stay the same asked for a probe of a bug, not of a promise.

## Decision

Drop the sentence when it says previously, formerly, used to, before this fix, or the old behaviour, when it says something was or were unchanged, when it says a bug where or that, when it says incorrectly or wrongly left unchanged, or when it says it fixes a bug or case where. A later sentence that only says results are unchanged is still a claim. A sentence that merely contains the word bug, and still promises that results stay the same, is still a claim.

## Alternatives and tradeoffs

- Drop every sentence that contains the word bug. That would also drop a real promise such as a bugfix that keeps results unchanged.
- Keep the old reading. The tool would ask for a probe of the bug description.

## What it means for you

Describe the old bug in its own sentence. A separate sentence that results stay the same is still checked. The bug description itself is not.
