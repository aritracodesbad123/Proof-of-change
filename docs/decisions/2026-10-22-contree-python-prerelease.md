# Keep pre-release and local tags in the Contree Python version

**Date:** 2026-10-22
**Status:** accepted

## What changed

- The version read from `python --version` inside Contree now keeps its pre-release tag (`a`, `b`, `rc`) and local tag (`+...`), for example `3.13.0rc1` instead of `3.13.0`.
- A pre-release Python on either side is a problem, so the check stops with "Contree Python check failed: ..." and the result is capped at could not verify.
- Because the full text is compared, `3.13.0rc1` on one side and `3.13.0` on the other is reported as a mismatch.
- Version text that does not fit this shape counts as unreadable, which is also a problem.

## Why

Before, the tags were cut off, so a release candidate looked like the final release. A pre-release Python can behave differently from the final one, and two sides that differ only by a tag were treated as the same.

## Decision

1. The reported version is recorded as printed, tags included.
2. Any pre-release on either side caps the result at could not verify, even when requires-python cannot be read.
3. A local tag alone is not a problem, but it must match exactly on both sides.
4. requires-python is still checked against the release numbers only.
5. Nothing is installed and the product core stays standard-library only.
