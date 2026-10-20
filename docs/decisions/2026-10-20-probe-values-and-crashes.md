# Probe values are written out, and a crash is not a difference

## What changed

The probe harness writes array-like values as lists, using tolist(), and uses the value's text form when that fails. A probe that crashes on the base side or the PR side is not adequate. The crash is not an unclaimed difference.

## Why

A value such as an array cannot be written as JSON on its own, so the probe crashed while printing what it saw. A crash on one side used to look like a behaviour change that no claim covered. It was a failure to print, not a change in the code under test.

## Decision

Every probe run uses this writer, including one that already imports the JSON library. tolist() is tried first. If the value has no tolist(), or tolist() raises, the text form is written instead. A side counts as crashed only when every run on that side failed to print usable output. One bad run of three does not. A crash on either side clears the probe's changed-line count and drops its observations from the verdict. A difference that both sides printed is not this case.

## Alternatives and tradeoffs

- Leave printing to each probe. An array would keep crashing the probe, and that crash would keep looking like a finding.
- Treat only a base-side crash as not adequate, and keep a PR-side crash as a finding. A print failure on the PR side would still look like an unclaimed change.

## What it means for you

A probe that sees an array records the list, or the text form if the list cannot be built. If the probe still crashes on either side, the result says it is not adequate. That crash is not reported as a change the pull request left unclaimed.
