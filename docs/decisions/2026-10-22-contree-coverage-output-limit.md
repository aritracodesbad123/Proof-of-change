# Contree coverage reports are trimmed to the changed files

**Date:** 2026-10-22
**Status:** accepted

## What changed

- Inside the Contree checkpoint, the coverage report is cut down to the files the pull request changed and printed compactly before it comes back.
- If the report still arrives without its end marker, the result says it was cut short by the Contree output limit, instead of "not valid JSON".

## Why

Contree caps the output of a command at about 64 KB. On a large project the full coverage report was longer than that, so it arrived cut off, failed to parse, and coverage was recorded as not measured even though the tests ran.

## Decision

1. Only the changed files are sent back; the coverage gate only reads those files anyway.
2. A cut-off report is still never counted as measured, so the check stays could not verify.
3. Nothing is installed and no package names are written into the check.

## Python version in Contree

- Before: in Contree mode the version choice compared against the Python of the machine running the check, and used that machine's installed Pythons to pick a version. Inside Contree the base image's Python is what runs, so the choice could be wrong (for example the machine has 3.14, the image has 3.12, and a 3.14 project was told "already met").
- Now: in Contree mode the current version is read from the base image tag, and any version that meets requires-python can be picked, because the setup step installs it inside Contree on both sides. If the image tag names no Python version, the wanted version is always set up.
