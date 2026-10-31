# Empty collection, quote marks, the pull-request title, and probes that miss the change

## What changed

Seven judging and report fixes, plus the report's source file.

1. When both sides collect no tests, a probe finding no longer turns the record into needs attention. The verdict stays could not verify.
2. The self-check compares each record's verdict with the summary and with the per-PR report. A disagreement fails the check. A failed known-answer replay is still allowed to show could not verify on purpose.
3. Loose quote matching treats `"`, `'`, `` ` `` and curly quotes as the same character. Paired Markdown is still removed first, so `` `code` `` still unwraps.
4. The pull-request title counts as a claim. "Don't raise IndexError" covers a difference where main raises IndexError and the pull request returns a value.
5. The collection line says "both sides" when both sides failed to produce results. A new record that never ran coverage says the coverage was not run. It does not say the record predates the coverage gate. An old record with no coverage block still does.
6. A probe that calls an internal helper (a function whose name starts with one underscore) must pass a parameter the diff added, or call a public entry point the diff now uses to pass it. Otherwise the probe is marked unable to reach the change.
7. A claim that expects a difference, whose only flagged result is "does not differ" on a probe marked unable to reach the change, is could not verify. A probe that did reach the change and still shows no difference is still needs attention.
8. `SOURCE.json` in the report folder stores `head_sha`, `base_sha`, `main_sha` (the main side that was tested, or the base when that is what was checked out), and `tool_commit` (the Proof-of-Change commit on the record).

## Why

A check can collect nothing on both sides and still have a probe that saw a difference. That used to become needs attention, which reads like a finding about the pull request, while the tests never ran. The per-PR report could then show could not verify because a pytest exit was unexplained, and the self-check skipped that row, so the run looked consistent.

A quote that only changed `"` to `'` was dropped. A title that says the code should stop raising an exception did not cover the observation that shows exactly that. A probe that called an internal helper with the old argument list never passed the new parameter, and a "does not differ" result on those inputs was scored as a contradiction.

A new record that stopped before coverage ran had no coverage block, so the report said it predated the coverage gate. The report's `SOURCE.json` named the run folder and not the two commits or the tool commit.

## Decision

- Empty collection on both sides (no JUnit results, or only collection errors) keeps could not verify even when a probe flags a difference. Tests that were collected and then skipped are not this case.
- The self-check reads the summary row, the written summary, and the per-PR report banner. They must show the record's verdict when that verdict is one of the four labels. A record with no verdict is not a disagreement. Two displays may still say could not verify on purpose: a failed known-answer replay, and a verified record whose own checks failed (that run is not trusted). A needs-attention record shown as could not verify fails the check.
- Quote marks are unified only after paired Markdown is stripped, and only on the loose path. A quote that changes a word still fails. A quote shorter than 20 characters, or one that loses more than a fifth of its characters, still has to match exactly.
- The title claim is added only for "don't raise X" (and the same shape: do not, should not, must not, never) where X looks like an exception name. It covers unclaimed differences of the shape "main raises X, the pull request returns a value". Other differences stay unclaimed.
- Internal helpers are names that start with a single underscore. `__init__` and a class name are public entry points when the diff shows them passing the new parameter. A probe that calls the helper with the new argument, or that calls such an entry point, is not marked unable to reach the change.
- That mark lowers a verdict only when the flagged observations are "does not differ" for a differs claim. A difference the probe did record still needs attention, and the reach note is included in the reason.

## Alternatives and tradeoffs

- Treating every "does not differ" result as could not verify would hide a probe that reached the change and found the claim false. The lower verdict is only for a probe that never passed the new argument and did not use the public entry point.
- Treating every quote character as identical before Markdown stripping would stop `` `code` `` from unwrapping. Stripping first keeps that rule.
- Putting the title claim on every observation would hide differences the title does not describe. Only the "main raises X, pull request returns a value" shape is covered.

## What it means for you

- A check whose tests collect nothing on both sides stays could not verify, and the reason says "both sides" when that is what happened.
- If the summary or a per-PR report shows a different verdict from `record.json`, the run's self-check fails. A known-answer replay failure is the exception.
- A claim quote that only changed quote marks is kept and marked `quote_match: loose`.
- A title such as "Don't raise IndexError ..." counts as proof when a probe shows main raising IndexError and the pull request returning a value.
- A new record no longer says it predates the coverage gate just because coverage did not run.
- A probe that calls `_helper(...)` without a new parameter the diff added is marked unable to reach the change. If that probe is the only check of a differs claim and the two sides agree, the verdict is could not verify.
- `SOURCE.json` next to the report lists both commits and the tool commit.
