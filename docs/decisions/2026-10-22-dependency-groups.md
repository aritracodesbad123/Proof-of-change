# Product checks install the project's dependency groups

**Date:** 2026-10-22
**Status:** proposed

## What changed

- A product check now reads every `[dependency-groups]` table entry (PEP 735) from main's `pyproject.toml` and installs the listed packages on both sides. No group name is special.
- `{include-group = "..."}` entries are followed. A group that includes itself, directly or through a loop, is read once.
- A line that names the project itself with extras (for example `project[all]`) is replaced by the lines of those extras from `[project.optional-dependencies]`, followed the same way. The project itself is never installed from the index.
- Every resulting line goes through the same refusal rules as the dependencies-only fallback: index options, URLs, git, editable installs and local paths are refused and recorded, not installed.
- Study runs are unchanged.

## Why

Many projects keep their test-time packages in a dependency group (often one that pulls the project's own extras). Those packages were never installed, so test modules failed to import and the check ended as a setup gap.

## Decision

1. Groups are read from main's files only; the pull request cannot add packages this way.
2. Only packages from the official index are installed from groups.
3. Product checks only.
