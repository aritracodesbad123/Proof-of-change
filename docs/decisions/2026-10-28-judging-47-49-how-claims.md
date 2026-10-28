# Judging: not_adequate probes count neither way, insertion anchors, id/text-linked observations, how-it-works claims

Date: 2026-10-28

## Decisions

- **47. A not_adequate probe never raises attention.** Its observations are dropped from the verdict entirely, not
  just its green ones, so the behaviour matches the note "its results do not count either way". A crashed probe keeps
  its red/amber results as before (its coverage is zeroed by the crash, not measured as missing the change).
  Why dropping its red and amber flags is safe: coverage is measured on the main side and the probe ran none of the
  changed main lines, so on its path main and the PR execute the same code. Any difference it reports comes from
  something other than the change (nondeterminism, set-up, environment), and a "does not differ" result says nothing
  about a change it never reached. Nothing is promoted by the drop: the probe is also never evidence for verified,
  and under the baselines with the AI-probe gate (the product default) a model probe that ran a changed line is
  still required, so a run whose probes are all not_adequate ends at could_not_verify, not verified. Under a
  baseline without that gate the tests alone decide, as for a run with no probe. A probe that does reach the change keeps every flag (test
  `test_47_real_flag_from_a_probe_that_reaches_the_change_survives`).
- **48. Pure insertions anchor on executable lines.** For a hunk that only adds lines, the main-side lines used for
  changed-line coverage are now the nearest non-blank, non-comment line before and after the insertion point. Before
  this, the line right before and after could be a blank line (which never runs) or a branch that does not run on the
  path the new code is on. Checked on a real case first: the anchors were a `continue` and a blank line; now they are
  the `continue` and the statement the new code runs before.
- **49. Id prefixes in any case or separator, and text-linked observations are advisory.** A claim whose cover is its
  own id also links observation names starting with the id followed by `.`, `-` or `_`, in any case (not `C10`, not
  `C1a`). In a model probe with claims, an observation that differs and matches no cover, but whose name starts with
  the exact full id of one of that probe's own claims, number included (`c2.` or `C2_` next to claim `C2`; `c9.`
  next to only `C1` still flags), is reported as advisory
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

## Follow-up (not in this change)

- `TypeError: x` on main versus `TypeError: y` on the PR currently counts as proven for a "differs" claim.

## Follow-up: no evidence any changed line ran caps at could_not_verify

If a run has probes, every probe ran 0 changed lines on the main side, and the tests' coverage was not measured or showed none, nothing shows the change was exercised. Such a run is capped at could_not_verify (`no_evidence_gate`, applied in `gate` and mirrored in `derive_verdict`). The cap only lowers a verified verdict; it never raises one. Test: a case shaped like a CLI fix whose two probes ran 0 of 5 changed lines and raised the same exception on both sides.

## Follow-up: fix 49, same shape as a proven sibling

An unclaimed difference whose shape matches a proven claimed sibling in the same probe (the same main-side exception type turning into a value on the PR side) is advisory, with the note "probably the claimed change, check" (`linked_by: "shape"`). It stays labelled unmentioned and visible, and advisory observations still hold a verified run at could_not_verify. A difference of any other shape, or one with no proven sibling, still flags.
