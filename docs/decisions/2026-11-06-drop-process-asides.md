# Drop an author's process asides at claim extraction

## What changed

Behaviour-claim extraction now skips a sentence that is the author's aside about
their own process, intent or what they did not change ("I left it untouched.",
"We kept that as is."). It must start with "I" or "we" plus a process verb and
name no behaviour word (results, output, behaviour, values, API, returns,
raises). Claim clean-up (rule 1) also drops claims about the PR's own test cases
passing or failing ("Two new test cases ... fail before the fix").

## Why

loguru #1515 got past setup but was held at could not verify because "I left it
untouched." (about a formatter warning) became a behaviour claim that needed a
probe. invoke #1097 had two of its four model claims about its own tests.

## Decision

Fix it at extraction. No verdict rule changes; real claims still need probes,
and a dropped claim that a probe flagged still blocks verified.

## Alternatives and tradeoffs

A wider "anything first-person" filter would also drop real claims like "I kept
the output unchanged", so the filter is narrow and keeps any sentence naming a
behaviour word.

## What it means for you

Fewer false "unverified behaviour claim" abstentions. invoke #1097's remaining
claims C1 and C4 are still unchecked: its probe crashed on an import of a module
that does not exist, which this change does not hide.
