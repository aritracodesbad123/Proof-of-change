# Product checks get their own flag, and compiled-only changes can't be verified on them

## What changed

Product checks (the console, request-a-check, Codespaces and the GitHub App) now pass their own `--product-check` flag. The coverage cap reads that flag instead of guessing from `--related-reports`. On a product check, a change that touches only compiled code (C, C++, Cython and similar) is capped at could_not_verify.

## Why

The rule for product checks is "verified only when coverage was measured". Coverage can't see compiled code, so a compiled-only change could still come out verified. Also, the cap was switched on by the related bug-report flag, so removing that flag would have quietly switched the cap off.

## Decision

- Add `--product-check`, set by every product route and nowhere else. A benchmark run or the daily study ignores it even if it is present.
- On a product check, a compiled-only change gets could_not_verify with the reason "This change is in compiled code that coverage can't measure, so it can't be marked verified".
- Study and daily runs are unchanged.

## Alternatives and tradeoffs

We could keep inferring product checks from the bug-report flag, but that ties a safety rule to an optional lookup. The cost of the compiled cap is that a well-tested compiled-only change can no longer reach verified on a product check.

## What it means for you

On the console, request-a-check, Codespaces or the GitHub App, a change only in compiled code shows could not verify with a plain reason. Study results don't change.
