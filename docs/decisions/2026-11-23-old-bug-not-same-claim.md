# A description of the old behaviour is not a promise that nothing changes

## What changed

Claim extraction no longer treats a sentence about the pre-pull-request behaviour, or about the bug being fixed, as a
promise that behaviour stays the same.

The claims prompt and its answer schema say so. `same` is only for a promise the pull request makes ("other inputs
are unaffected", "existing behaviour is preserved"). A sentence that describes the old behaviour is `base`, or it is
left out. A check after the model answers rewrites a `same` answer that is really the old behaviour, so a wrong
answer is still corrected. Judging does the same check on a claim that was already saved as `same`: a difference
against that sentence is not a broken promise, and a match is not proof that nothing changed.

The wording decides. A contrast such as "changes X but leaves Y unchanged", "still sized from ...", "returned []
before", "previously", "used to", "currently", "before the fix", "on main", and a problem statement that explains a
fault ("narrower ... because") are the old behaviour. A sentence that also states the new behaviour, or that speaks
about both sides, stays an ordinary claim. Nothing is special-cased to one repository.

## Why

Pull requests often open by describing the bug in the present or the past: the filter leaves a cached value
unchanged, the title is still sized from every column, the call returned an empty list before. Those words were
read as "the pull request promises no change". The probe then saw the fix, which does change that behaviour, and
reported the fix itself as a regression.

A promise that some other behaviour is unaffected is a different sentence. If that promise is broken, the check
still has to say so.

## Decision

Keep the old-behaviour sentence out of the "no change" check. Do not drop a real preservation promise, and do not
turn a real break into a pass. Removing the misread sentence does not by itself mark a run verified. The tests, the
other claims, and the existing gates still decide. If only the tests remain, those gates decide, including the rule
that a verified result needs a probe that ran a changed line.

The narrow shape "Before the fix, X raises/returns Y" keeps the reading it already had.

## Alternatives and tradeoffs

Dropping the sentence entirely, and then treating the probe's difference as unclaimed, would still flag the fix.
Keeping the sentence and checking it only as "the two sides must differ" would flag a run where that one observation
happened to agree. Neither is the check we want. The sentence is kept as a description of the base side and is not
scored as a promise.

A short list of phrases will miss some bug reports and will leave those on today's reading. It will not hide a
sentence that promises behaviour is preserved.

## What it means for you

A pull request that describes the bug with "unchanged", "still", or "before" is no longer marked as breaking a
promise it did not make. A pull request that says other inputs are unaffected is still checked, and a real change
there still needs attention. A saved record is re-judged from the claim text. The stored file is not rewritten, and
claim extraction is not run again, because that would call the model.

## Replay of saved records

The runs branch holds 258 `record.json` files (4 November 2026 through 23 November 2026). Each file was re-judged
with the verdict code from before this change and with this change. No model was called. 170 files had a verdict and
probe items and were judged. 88 had no probe items, so there was nothing to re-judge. 167 judged files were
unchanged. 3 changed. 0 errored.

All 3 changes are `needs_attention` to `verified`. In each one the only finding that needed attention was a sentence
describing the old bug, read as a promise of no change. After that sentence is not scored as a promise, the tests
that fail on the base and pass on the pull request, the other proven claims, and a probe that ran a changed line
already meet the existing verified gates. No other transition happened.

- psf/requests #7413 (4 November). The sentence was "Before the fix, HTTPDigestAuth.build_digest_header() used only
  .path and .query, causing the uri field to be truncated." Claims about the fix itself were already proven.
- andialbrecht/sqlparse #852 (9 November). The sentence was "The non-UTF-8 fallback currently decodes via
  unicode-escape." The claim that inputs without backslashes stay byte-identical was already proven, and it is
  still checked.
- prettytable/prettytable #557 (23 November). The title "still sized from all columns" and the table "narrower
  because the hidden column is counted" described the bug. The claim that the selected columns are what the width
  uses now was already proven.

andialbrecht/sqlparse #934 stays `needs_attention`. Its sentence about the cached `normalized` value is no longer a
broken promise, and two other findings remain.

Held-out records did not move. mahmoud/boltons #751 and #758 stay `verified`. #752 stays `could_not_verify`. #803
has no probe items, so it was not re-judged; its stored verdict stays `could_not_verify`. The two known misses named
in the narrow cross-run note (mlxtend #1229 and skrub #2319) are not in these saved records.
