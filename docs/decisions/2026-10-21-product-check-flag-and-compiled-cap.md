# Product checks get their own flag, and changes touching compiled code can't be verified on them

## What changed

Product checks (the console, request-a-check, Codespaces and the GitHub App) now pass their own `--product-check` flag. The coverage cap reads that flag instead of guessing from `--related-reports`. On a product check, any change that touches compiled code (C, C++, Cython and similar), even mixed with Python, is capped at could_not_verify.

## Why

The rule for product checks is "verified only when coverage was measured". Coverage can't see compiled code, so a change touching compiled code could still come out verified, even when its Python lines were measured. Also, the cap was switched on by the related bug-report flag, so removing that flag would have quietly switched the cap off.

## Decision

- Add `--product-check`, set by every product route and nowhere else. A benchmark run or the daily study ignores it even if it is present.
- On a product check, any change touching compiled files gets could_not_verify with the reason "This change touches compiled code that coverage can't measure, so it can't be marked verified", followed by the compiled file names.
- Study and daily runs are unchanged.

## Alternatives and tradeoffs

We could keep inferring product checks from the bug-report flag, but that ties a safety rule to an optional lookup. The cost of the compiled cap is that a well-tested change touching compiled code, even with measured Python coverage, can no longer reach verified on a product check.

## What it means for you

On the console, request-a-check, Codespaces or the GitHub App, any change touching compiled code shows could not verify with a plain reason. Study results don't change.
