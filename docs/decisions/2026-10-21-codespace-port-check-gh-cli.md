# Codespace port check: install the GitHub CLI, name the Codespace, and a console code when the port cannot be read

**Date:** 2026-10-21
**Status:** accepted

## Problem

In a real Codespace the GitHub CLI (`gh`) was not installed, so the console could not read port 8787's visibility. The fail-closed rule then kept sign-in on, and judges were stuck on a sign-in page, because email, Google and GitHub sign-in are not configured in a Codespace.

## What changed

- The dev container installs the GitHub CLI with the `ghcr.io/devcontainers/features/github-cli:1` feature. No privileged mode or extra capabilities.
- The console and `.devcontainer/start-console.sh` call `gh codespace ports -c "$CODESPACE_NAME" --json port,visibility`, naming the Codespace with `-c` whenever `CODESPACE_NAME` is set.
- When `gh` is missing, the sign-in page says plainly "GitHub CLI missing".
- The fail-closed rule is unchanged: sign-in is skipped only when the port list is read and port 8787 is not public. A public port always refuses.

## Console code fallback

The Codespace's built-in `GITHUB_TOKEN` is a repository-scoped integration token. GitHub CLI reports show the Codespaces API answering it with `HTTP 403: Resource not accessible by integration`, so listing ports with it is likely to fail even with `gh` installed.

When the port list cannot be read, the console creates a random 128-bit code in an owner-only file, `/tmp/poc-console-code` (mode 0600), inside the Codespace. The sign-in page asks for it. Anyone who can run `cat /tmp/poc-console-code` already controls the Codespace, so the code proves access to the Codespace itself. It does not trust the port.

- The code is never printed, logged or returned by the API.
- It only works in a Codespace or single-user console, and never while the port is known to be public. A port that turns public ends existing code sessions.
- Wrong codes are compared in constant time and capped per console start.
- On any other host the route refuses, and normal sign-in applies.
