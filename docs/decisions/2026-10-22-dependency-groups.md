# Product checks install the project's dependency groups

**Date:** 2026-10-22
**Status:** accepted

## What changed

- A product check now reads every `[dependency-groups]` table entry (PEP 735) from main's `pyproject.toml` and installs the listed packages on both sides. No group name is special.
- `{include-group = "..."}` entries are followed. A group that includes itself, directly or through a loop, is read once.
- A line that names the project itself with extras (for example `project[all]`) is replaced by the lines of those extras from `[project.optional-dependencies]`, followed the same way. The project itself is never installed from the index.
- Every resulting line goes through the same refusal rules as the dependencies-only fallback: index options, URLs, git, editable installs and local paths are refused.
- Fail closed: if any group line is refused, the check stops before installing anything and ends as could not verify, with an `unsupported:` reason that names the lines. The rest of the groups is never installed on its own.
- A table that PEP 735 does not allow also ends the check as could not verify, naming the problem: an `include-group` that names a missing group, two group names that are the same after normalization (for example `test-stuff` and `Test_Stuff`), and entries that are neither a requirement string nor a table with only `include-group` (for example a number).
- The stop applies on every install route of a product check: the local install with retries, Contree, and the nightly route.
- Study runs are unchanged.

## Why

Many projects keep their test-time packages in a dependency group (often one that pulls the project's own extras). Those packages were never installed, so test modules failed to import and the check ended as a setup gap.

## Decision

1. Groups are read from main's files only; the pull request cannot add packages this way.
2. Only packages from the official index are installed from groups; anything else stops the check instead of being skipped.
3. Product checks only.
