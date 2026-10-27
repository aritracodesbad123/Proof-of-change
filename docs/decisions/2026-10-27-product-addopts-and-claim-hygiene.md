# Product checks: keep the project's pytest addopts, clean up model claims, refuse closed pull requests

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
   "still", "continues to", "as before", "will not", "does not") is typed `same`, unless it also says the old
   behaviour stops ("no longer", "anymore", "now", "instead"). The probe is judged again with the corrected type, so
   a real difference on such a claim becomes a false claim (needs attention).
4. **Claims from test outcomes are dropped.** A claim that describes a test run (a test or test suite passing, or a
   count of tests passed) is not something the pull request claims about its behaviour, so it is removed. A model
   probe whose every claim was removed is removed from the deciding probes. If that probe had flagged a difference,
   the run cannot be verified (fail closed), since nothing else may have probed what it saw.
5. **Closed or merged pull requests are refused.** Before any lookup, install or run, a product check of a pull
   request whose state is not open stops with could not verify and the plain reason "refused: this pull request is
   closed or merged, not open, so it was not tested". The reason is also kept in `pr_state_refusal`.
   Benchmark and known-answer runs test fixed commits of merged or closed pull requests on purpose. Their runner
   passes `--known-answer-case`, which records the state in `pr_state_note` instead of refusing. Only a
   user-requested product check (without that flag) is refused. There is no per-project list.

Each clean-up is written to the record (`probes.claim_hygiene` and `claim_hygiene_note`), so a reader can see what
was changed and why.

## Consequences

- Projects whose tests depend on their own addopts can now be measured. A project whose addopts add something the
  check cannot satisfy may now fail differently; that shows up in its test log as a setup problem.
- None of the claim rules can turn a run into verified on its own: tests still decide, and dropped or retyped claims
  can only remove a false flag or add a stricter one. An advisory difference holds the run at could not verify.
- The phrase lists are deliberately small and may miss wording. A missed phrase leaves today's behaviour in place.
