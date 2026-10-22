# Contree setup scripts run under bash, and setup failures say what really failed

Date: 2026-10-22

## Problem
Contree runs each command with `/bin/sh`. On the Debian-based Python image that is dash, which (in the version
on that image) rejects `set -o pipefail` with exit code 2. Every Contree check therefore stopped while building
the main checkpoint, before any test ran. The report then told the user to check their Nebius key and project
ID, which was wrong, and the sandbox's error output was not kept, so the cause was hard to find.

## Decision
- Every Contree command is wrapped in a small POSIX script: if bash exists it runs the original script with
  `bash -c`, so `set -euo pipefail` keeps working; if bash is missing it runs the script under sh with
  `pipefail` removed (`set -eu`).
- A failed checkpoint build reports the exit code and the last part of the error output, with the Nebius key,
  project ID and bearer tokens removed.
- The credentials hint is shown only when the Contree API itself refused access (an auth error class or HTTP
  401/403).
- The run record's `contree` entry keeps `exit_code`, `stderr_tail` and `auth_error`.

## Tests
`tests/test_contree_shell.py` runs the generated setup script under plain sh (dash when installed), checks that
pipefail is active under bash, checks the no-bash fallback, and covers the failure reason, redaction, the auth
case and the record fields.

## Not changed
Verdict rules. A setup failure is still could not verify, and nothing from the pull request runs locally.
