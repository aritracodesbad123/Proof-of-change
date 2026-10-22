# Record which Python ran on each Contree side

**Date:** 2026-10-22
**Status:** proposed

## What changed

- After the main and PR checkpoints are built, a product check runs `python --version` from each side's Contree checkpoint, the same place the tests run.
- The run record keeps the result under `contree.python`: the main version, the PR version, the requires-python taken from main's files, and any problems.
- If a side's version cannot be read, or does not satisfy requires-python, the check stops with "Contree Python check failed: ..." and the result is capped at could not verify.
- Main and PR must also report exactly the same full version (for example 3.12.7 on both). If they differ, the check stops with "Contree Python check failed: main ran X, PR ran Y", even when the project declares no requires-python.

## Why

The version choice for Contree was fixed earlier, but nothing confirmed which Python actually ran inside the sandbox. A project that needs 3.14 could have run on an older Python and still shown up as a normal result.

## Decision

1. The version is read inside Contree, never from the machine running the check.
2. requires-python comes from main's checkout only, so a pull request cannot loosen it.
3. Both sides must run the same full Python version, so a difference between them can't be mistaken for an effect of the pull request.
4. An unreadable or mismatched version is a problem, never a normal result.
5. Study runs are unchanged; this applies to product checks only.
6. Nothing is installed and no versions or package names are written into the check.
