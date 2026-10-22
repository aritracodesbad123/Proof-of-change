# Missing tools are installed when a check starts

**Date:** 2026-10-22
**Status:** accepted

## What changed

A GitHub Codespace without `uv` crashed every check with `FileNotFoundError: uv`.

- `uv` is now a declared dependency of Proof-of-Change in `pyproject.toml`. The version lives only there.
- `poc/tool_setup.py` reads that declared list at console start and at the start of every check. Anything missing is installed with one `python -m pip install` call, tried up to 3 times. After that the check stops with a plain-words error, not a traceback.
- Every `uv` command gets its path from `tool_setup.uv_bin()`.
- What was installed is recorded in the check record (`tool_setup`) and noted in plain words in the setup notes.

## Why

Setup scripts can be skipped or fail, so the code makes sure of its own tools instead of relying on them. Installs come only from the project's declared requirements, with pinned versions, never from an installer script.

## Decision

1. Tools are declared once, in `pyproject.toml`.
2. `ensure_tools()` installs whatever is missing, with 3 tries, then a plain error.
3. `git` is checked but not installed; a missing `git` gives a plain error.
