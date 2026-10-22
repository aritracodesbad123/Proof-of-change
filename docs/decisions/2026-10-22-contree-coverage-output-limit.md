# Contree coverage reports are trimmed to the changed files

**Date:** 2026-10-22
**Status:** proposed

## What changed

- Inside the Contree checkpoint, the coverage report is cut down to the files the pull request changed and printed compactly before it comes back.
- If the report still arrives without its end marker, the result says it was cut short by the Contree output limit, instead of "not valid JSON".

## Why

Contree caps the output of a command at about 64 KB. On a large project the full coverage report was longer than that, so it arrived cut off, failed to parse, and coverage was recorded as not measured even though the tests ran.

## Decision

1. Only the changed files are sent back; the coverage gate only reads those files anyway.
2. A cut-off report is still never counted as measured, so the check stays could not verify.
3. Nothing is installed and no package names are written into the check.
