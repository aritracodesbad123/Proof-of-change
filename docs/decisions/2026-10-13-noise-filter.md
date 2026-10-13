# Ignore noise and warning-only differences

## What changed

A probe (a small script run on the old and the new code) is run several times on each side. Two kinds of
difference no longer count as a problem:

1. **Noise.** If an observation gives different results between runs on the *same* side, it is noise (timing,
   ordering, random effects). Before, that alone made the result "needs attention". Now it is listed in the
   report as "ignored as noise" and does not decide the verdict.
2. **Warning-only differences.** If the only differences are about warnings (an observation whose name mentions
   a warning), they do not count as a break on their own. If there is also a real difference, the warning
   differences are still shown alongside it.

## Why

Warnings and run-to-run jitter changed the verdict on pull requests whose real behaviour did not change. A check
that cries wolf gets ignored, so these differences are shown but no longer decide the verdict.

## Trade-offs

- A real problem that only shows up as a new warning, or only sometimes, will now be missed by the probes. The
  project's own tests still run and still count.
- "Mentions a warning" is a simple name rule. It is written in general terms and was not tuned on any benchmark
  case.
