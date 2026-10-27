# Product checks: link claim ids in code, unlinked probes are advisory, quotes grounded without Markdown

**Status:** proposed

Date: 2026-10-27. Applies to the product route only (`--product-check`). The study route is unchanged.

## Context

A root-cause check of the 27 Oct product run found three generic causes of wrong verdicts:

- The model often writes a claim's `covers` as the claim id (`"C1"`, `"C1*"`, sometimes in another case than the
  observation names) instead of observation-name patterns. Matching was exact and case-sensitive, so `C1` never
  matched `C1.leftover_count` and never matched `c1.empty`. Nine of twenty claimed probes were rejected that way.
- A rejected probe still counted against the pull request: its differences were scored as "differs and no claim
  covers it" and gave needs attention, even when the difference was the claimed fix.
- A claim was dropped when its quote lost the pull request's Markdown (backticks, bold) on the way through the
  model, because quotes were compared as exact text.

## Decision

1. **Claim ids link in code.** On a product check, a cover equal to its claim id, optionally ending in `*`, links
   the observation named exactly that id or starting with `<id>.`, ignoring case. It never links a longer id:
   `C1` does not link `C10` or `C10.x`. Other cover patterns are matched ignoring case. The covers as written are
   kept on the claim (`covers_as_written`), each repaired link is listed in `probes.claim_hygiene.relinked`, and the
   probe is judged again. A link only says which claim an observation belongs to. The claim still has to hold: a
   claim expecting a difference that does not appear still needs attention.
2. **Unlinked probes are advisory.** A model probe whose claims, after rule 1, link none of its observations is
   treated like a probe with no claims: its unclaimed differences are kept, marked `advisory`, listed in
   `unlinked_probes`, and do not raise needs attention. Any advisory difference still caps the result at could
   not verify, so such a probe can never help a pull request reach verified. Failing tests still give needs
   attention. A probe that links at least one claim still flags every unclaimed difference.
3. **Quotes are grounded without Markdown.** A claim quote that is not found as written is compared again after
   removing backticks, `*` and `_` and unifying dashes, arrows and quotes, on both sides. Different words are never
   matched. A claim kept that way carries `quote_match: "loose"`, and the record lists every such match in
   `probe_plan.model_loose_quote_matches`.

Claims that expect a difference and match no observation are now counted after rule 1, then kept as `held_back`
through the other clean-up rules as before. Retyping or dropping a claim still never lifts that cap. Rule 1 can
lift it, because a repaired link means the claim was checked.

Of these rules, only rule 1 can help a run toward verified, and only by crediting a claim whose observation was
named after it and showed the claimed result. Rules 2 and 3 never make a result verified on their own.

## Consequences

- Claimed fixes that were flagged as unclaimed differences can now be proven, and probes with no usable link no
  longer turn a pull request into needs attention.
- More claims survive grounding, so more probes are written. A loosely matched quote is visible in the record for
  review.
- There are no per-project rules.

## Measurement

Each rule was replayed on saved records (frozen benchmark records and the held-out checked pull requests), alone
and combined. None added a miss. Rule 3 changes which claims reach the probe writer, so its effect on verdicts needs
live runs; its replay counts recovered quotes only.
