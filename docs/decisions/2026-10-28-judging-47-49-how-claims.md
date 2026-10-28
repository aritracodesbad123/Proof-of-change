# Judging: not_adequate probes count neither way, insertion anchors, id/text-linked observations, how-it-works claims

Date: 2026-10-28

## Decisions

- **47. A not_adequate probe never raises attention.** Its observations are dropped from the verdict entirely, not
  just its green ones, so the behaviour matches the note "its results do not count either way". A crashed probe keeps
  its red/amber results as before (its coverage is zeroed by the crash, not measured as missing the change).
- **48. Pure insertions anchor on executable lines.** For a hunk that only adds lines, the main-side lines used for
  changed-line coverage are now the nearest non-blank, non-comment line before and after the insertion point. Before
  this, the line right before and after could be a blank line (which never runs) or a branch that does not run on the
  path the new code is on. Checked on a real case first: the anchors were a `continue` and a blank line; now they are
  the `continue` and the statement the new code runs before.
- **49. Id prefixes in any case or separator, and text-linked observations are advisory.** A claim whose cover is its
  own id also links observation names starting with the id followed by `.`, `-` or `_`, in any case (not `C10`, not
  `C1a`). In a model probe with claims, an observation that differs and matches no cover, but whose name starts with
  a claim id of the same form as the probe's claim ids (`c2.` or `C2_` next to `C1`, `C3`), is reported as advisory
  ("linked by claim id, check") instead of unclaimed. A word shared with a claim's text is deliberately not a link:
  measured on saved records it hid a real catch (a probe named after the patched function, with every claim's text
  naming that function). An advisory observation still holds a verified run at could_not_verify. A difference
  tied to no claim at all still flags (fix 42 unchanged).
- **How-it-works claims need no difference.** A claim that only says which code the fix goes through ("is processed
  by `_as_list()`", "now calls `x`"), naming that code, does not fail when calling it gives the same result on both
  sides: the observation is not_testable and the claim is not held back as unmatched. A claim describing a behaviour
  change that shows none still flags.

## Tests

`tests/test_judging_47_49.py`, with a real-bug test for each fix that still comes out needs_attention; updated
expectations in `tests/test_probe_adequacy.py`, `tests/test_claim_linking.py` and
`tests/test_probe_imports_and_output.py`.

## Measurement

Rejudged every saved record (frozen benchmark plus held-out checked pull requests) before and after; the list of
changed verdicts is in the pull request description. No known catch is lost.
