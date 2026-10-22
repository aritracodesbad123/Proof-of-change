# Records may say coverage was not measured

**Date:** 2026-10-22
**Status:** proposed

## What changed

- Schema revision 16 adds `not measured` to the allowed values of `coverage.status`.

## Why

The check already writes `not measured` when a coverage report is missing or unusable, but the schema did not allow it, so those records failed the schema check even though they were correct.

## Decision

1. `not measured` is a valid coverage status.
2. Nothing becomes required, so records from earlier revisions stay valid.
3. A record that says `not measured` still never counts as measured coverage.
