# "Existing behaviour preserved" next to an edited pattern becomes an expect-same claim on past-boundary inputs

Date: 2026-10-29. This is option B, which was deferred in `2026-10-29-edited-pattern-boundary-probes.md`.

## Problem

On the rich #4147 check, the claims step read "updated to correctly handle adjacent tags while preserving existing
behavior" as one claim, C3, with `expect: differs`. Once the probes read the returned value (#187), they show the
loss on inputs just past the old match: tag spans on base, none on the PR. Linked to the model's own C1 and C3,
both `differs`, those differences count as the claimed change and the check comes out verified. With no claim
links, the live claim-hygiene step makes them advisory, so the check is could_not_verify.

## Change

New module `poc/boundary_claims.py`, product route only. It runs in the live settle step
(`settle_boundary_claims` after `settle_probes`) and in `rejudge`.

- **Seed.** It runs only when `probe_plan.model_boundary_rule` lists an edited existing pattern. For each testable
  claim whose text says existing behaviour is kept (`PRESERVE`: "preserving existing behavior", "existing behaviour
  is preserved/kept/unchanged", "without changing existing ...", "keeps the existing behaviour"), it adds
  `<id>-kept` with `expect: same`. A claim that only re-runs the PR's own test is excluded
  (`boundary_probes.reruns_pr_test`: a test-outcome sentence, or one naming a test the diff adds).
- **Past boundary.** An input counts as past the boundary when an old pattern matches it and some text is left
  outside every match. A single trailing newline does not count.
- **Inputs.** Inputs come only from the probe's frozen source: dict literals of string names to string inputs. An
  observation is tied to an input by the part of its name after the last dot.
- **Effect.** A past-boundary observation that differs between base and PR becomes `false_claim` under the seeded
  claim (red). It loses any advisory mark, because the PR text itself promised it would not change. Same
  observations are left exactly as they were. Nothing is marked proven, and no verdict is ever raised.

## Offline proof (no live run, no credits)

The tests replay the live record from the 10:31 IST run. The two probes' runs are replaced by the outputs of the
same probes fixed only on the call line (#187 proof: rich 9d8f9a37 and 3bd56b51, 3 runs each). Claims are left as
the model wrote them. The record goes through claim hygiene (the live settle step), then `rejudge` and `final()`.

| Variant | Seeded claim off | Seeded claim on |
|---|---|---|
| Claims as written (`[]`, no links) | could_not_verify | needs_attention: false_claim on followed, preceded, newline, pre_newline (both probes), under C3-kept |
| Probes linked to the model's C1/C3 (`differs`) | verified | needs_attention: the same 4 inputs, false_claim under C3-kept |

The claimed change, `adjacent` and `single`, is never flagged. Fixtures are in `tests/fixtures/boundary_claims/`.
The diff there is the PR's own 2-file change.

## Safe cases

On all 13 safe candidates, nothing is seeded even when given a claim that says behaviour is preserved, because no
existing pattern is edited. This is a fixed parametrised test in `tests/test_boundary_probes.py`.

## Mutations

14 mutations, all killed:

- seeding without an edited pattern
- untestable claims seeded
- the preserve wording ignored
- PR-test re-runs allowed
- a bare trailing newline counted
- any match counted
- same observations flagged
- every input flagged
- the advisory mark kept
- applied on the study route
- non-string tables read
- the "keep" wording dropped
- the rejudge wiring removed
- the live wiring removed

## Risks and limits

- **Fix aimed at the boundary.** A PR whose real fix is the past-boundary text, and that also says it preserves
  behaviour, would be flagged. It needs both the edited pattern and the explicit preserve sentence.
- **Input tables.** Only inputs written as a literal string table are seen. Probes built in other ways are not
  covered, and stay as they are.
- **Not shown live.** Whether the live claims step plus probes produce this is not yet shown. No live run was made.

## Route wiring tests

`tests/test_boundary_settle_routes.py` drives each live route (the local nightly route in `test_pr` and
`_contree_only_pair`) with its build, test and probe steps stubbed, and asserts `settle_boundary_claims` runs once,
after `settle_probes`, with that check's directory. Removing the call from either route fails its test
(both drop mutations checked).
