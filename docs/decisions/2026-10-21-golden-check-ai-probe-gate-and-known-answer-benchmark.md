# The golden check applies the AI-probe gate, and a known-answer benchmark runs on every change

## What changed

1. **Golden check uses the same gates as a real run.** When the golden check re-works out a recorded pull request's
   verdict, it now applies the AI-probe gate after the coverage gate, just as a real full run does. Under a mode
   with AI-written probes, "verified" now needs an AI-written probe that actually ran a changed line. A docs-only
   or docstring-only change has no such line, so the golden check can no longer call it verified in full mode.
   It also passes the docstring-only flag to the verdict rules, as a real run does. We chose to add the gate
   rather than leave docs-only and docstring-only cases out of the golden check, because the gate is one shared
   function and adding it makes the two paths agree for every case, not only those.
2. **Known-answer benchmark.** `evals/bench12/` holds small made-up pull requests on a tiny package. Each case has
   the code before and after, the claim, and the recorded evidence a run would have (per-run test results, probe
   observations, install errors). The expected verdicts sit in a separate answer key that only the scoring step
   reads; the step that runs a case refuses any answer file. Cases cover: kept, broken, failed install,
   typing-only, flaky on both sides, flaky only on the base, unstable only on the pull request (repeating and all
   different), a claim the change does not touch, a false claim, a hidden regression next to a fix, a test timeout,
   an install timeout, the setup-rerun coverage check, and a docs-only change on both the daily and single-check
   routes. The tests run them on every change, offline and without a model or keys. Each case is also re-derived
   through the golden check, so the two paths cannot drift apart unnoticed.

## Frozen answers worth noting

- A run where the pull request's three results are pass, fail and error is could not verify: too mixed to call a
  regression, and never verified.
- The kept case is verified only because a probe ran a changed line; the same case without that probe is could not
  verify in full mode and verified in tests-only mode.
- A docs-only change is skipped in the daily run and could not verify on a single check in full mode.
- The flaky-on-both-sides case uses a real code change. The docstring-only form is not frozen while the
  docstring-only rule is still under discussion.

## Trade-offs

- Fewer golden "verified" answers in full mode for changes no probe reached. That is the same honest answer a real
  run gives.
- The benchmark checks the verdict rules on recorded evidence; it does not install packages or call a model, so
  install and model behaviour are covered elsewhere.
