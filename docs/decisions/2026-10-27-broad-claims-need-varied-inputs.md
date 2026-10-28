# Broad "nothing else changes" claims need several varied inputs

Status: accepted

Date: 2026-10-27

## Context

A pull request often says its change keeps everything else the same ("while preserving existing behavior",
"nothing else changes", "no other behaviour changes"). Such a claim is about every input the changed code accepts.
A product check could prove it with one probe on one input that came out the same on base and head. A change that
breaks other inputs was then reported as verified, which is a known miss.

## Decision

Product checks only (`poc/broad_claims.py`):

1. When a testable claim that expects "same" matches a generic broad phrase list, the probes prompt gets an extra
   paragraph naming those claim ids. It asks for at least 3 (better 6 or more) separate observations per broad
   claim, each on a different input, chosen from the base-side code and not only the PR's own example. The full
   result is recorded for each input, so plain code compares base and head on every input.
2. After the probes run, a broad claim linked to fewer than 3 distinct observations is held back. A verified result
   then becomes could_not_verify with the reason "broad 'nothing else changes' claim(s) ... were checked on fewer
   than 3 varied inputs". A difference on any input is decided by the existing probe rules (needs attention).

The rule only lowers a verified result. It never raises a verdict. The phrase list names no project or package.
Study runs never call the module, so the study prompt and study records are unchanged.

## Consequences

- A broad claim is now checked against several inputs instead of one probe.
- A model that writes only one input for a broad claim gives could_not_verify, not verified.
- The minimum is a fixed count of observations. It does not judge how different the inputs are.
