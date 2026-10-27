# Product checks: keep the project's pytest addopts, clean up model claims, refuse closed pull requests

**Status:** accepted

Date: 2026-10-27. Applies to the product route only (`--product-check`). The study route is unchanged.

## Context

A verification of the final product rerun found one setup failure and three wrong or weak verdicts, all from
generic causes:

- A project whose test run needs a plugin that its own pytest configuration loads (`addopts = ["-p", ...]`)
  collected nothing on either side, because every test command passed `-o addopts=`, which blanks the project's
  addopts. The plugin's config options were then unknown and collection failed.
- A model probe with no claims attached labelled the pull request's own intended change as "differs and no claim
  covers it", turning a correct result into needs attention.
- A claim that says something stays the same ("will NOT bypass the proxy for another port") was typed as expecting
  a difference, so the correct "no difference" was flagged.
- Claims the pull request does not make ("the regression test passes", "84 tests passed") were extracted and probed.
  Their probes only restated the fix and produced a misleading finding.
- A closed pull request was tested as if it were open.

## Decision

1. **Project addopts kept.** On a product check the test run, the test-coverage run and their Contree versions no
   longer pass `-o addopts=`, so the project's own pytest settings apply. Nothing is added per project. The study
   route still blanks addopts, as before.
2. **Claim-less model probes are advisory.** A model probe with an empty claims list cannot tell which differences
   the pull request intended. Its "differs and no claim covers it" observations stay in the record with their label,
   are marked `advisory`, and do not raise needs attention. They are still unexplained, so a pull request with
   one can never be verified: it is held at could not verify. A probe that has claims still flags any unclaimed difference.
3. **"Stays the same" claims expect same.** A claim whose text says behaviour is kept ("unchanged", "preserved",
   "as before", "unaffected", "continues to", "will not") is typed `same`, unless it also says the old behaviour
   stops or names an error ("no longer", "anymore", "now", "instead", "raise", "crash"). Wording such as "does not
   raise", "is not merged" or "still" is left alone, because it usually describes the fix. The probe is judged again
   with the corrected type.
4. **Claims from test outcomes are dropped.** A claim whose subject is a test run (a regression, unit or new test
   passing, the test suite passing, "N tests passed", CI green) is not something the pull request claims about its
   behaviour, so it is removed. A model probe whose every claim was removed is removed from the deciding probes. If
   that probe had flagged a difference, the run cannot be verified.
5. **Live checks refuse closed or merged pull requests.** Only live checks (the console, the GitHub App and the
   request worker) pass `--live-check`. Such a check reads the pull request's state from GitHub just before running.
   If it is closed or merged, has no state, or the read fails, the check stops with could not verify and a plain
   `refused: ...` reason (also kept in `pr_state_refusal`), before any lookup, install or run. It never crashes.
   Benchmark, known-answer and replay runs do not pass the flag, so their fixed merged or closed cases still run.
   There is no per-project list.

Two holds keep the clean-up from ever making a run look better than its evidence:

- **Unclaimed differences hold the run.** If any advisory difference exists and the verdict would be verified, it
  is capped at could not verify.
- **Unmet claims hold the run.** Claims that expected a difference and matched no observation before the
  clean-up are kept as `held_back`. Retyping or dropping such a claim never lifts that cap.

Each clean-up is written to the record (`probes.claim_hygiene` and `claim_hygiene_note`), so a reader can see what
was changed and why.

## Consequences

- Projects whose tests depend on their own addopts can now be measured. A project whose addopts add something the
  check cannot satisfy may now fail differently; that shows up in its test log as a setup problem.
- The claim rules can change a verdict in one direction only for a claim that already matched an observation: a
  retyped "stays the same" claim whose behaviour really stayed the same is now proven instead of flagged. They can
  never lift the unmet-claim cap, never let an advisory difference through as verified, and never hide a test
  finding.
- The phrase lists are deliberately small and may miss wording. A missed phrase leaves today's behaviour in place.
