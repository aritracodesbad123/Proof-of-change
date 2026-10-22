# Accept a git worktree when stamping the Proof-of-Change commit

**Date:** 2026-10-22
**Status:** proposed

## What changed

`resolve_poc_commit` treats the checkout as a git checkout when `.git` exists, either as a folder or as a file. A git worktree has a `.git` file that points to the main repository.

## Why

A run started from a worktree used to fall through to `POC_COMMIT` or `RENDER_GIT_COMMIT`, or stop with "this checkout has no .git", even though it is a real git checkout.

## Not changed

Images without `.git` still need `POC_COMMIT` or `RENDER_GIT_COMMIT`. The fast-forward to origin/main and its clean-tree check are unchanged.
