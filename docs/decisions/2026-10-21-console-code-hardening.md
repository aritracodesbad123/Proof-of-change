# The Codespace console code is hardened: no links, Codespace only, public port ends sessions

**Date:** 2026-10-21
**Status:** accepted

## Context

When the Codespace console cannot confirm that port 8787 is private, sign-in stays on and the console offers a one-time console code instead. The code lives in `/tmp/poc-console-code` inside the Codespace, readable only by its owner. A review of that fallback found four gaps worth closing.

## Decision

1. **The code file is opened without following links.** Reads and the existence check use `O_NOFOLLOW` and `fstat`. If the path is a symlink, is not a regular file, is not owned by the console's user, or is not mode `0600`, the console unlinks it and creates a fresh one with `O_CREAT | O_EXCL | O_NOFOLLOW` and mode `0600`. A file planted by someone else is never trusted and its contents are never accepted as the code.
2. **`POC_SINGLE_USER` only counts inside a Codespace.** Skipping sign-in and the console-code prompt both require `CODESPACES` to be set. Setting `POC_SINGLE_USER` on a hosted console does nothing, so the code prompt can never appear there.
3. **A public port ends every code session.** As soon as the console sees port 8787 as public, all console-code sessions are deleted, not just refused for that request. Turning the port private again does not bring them back; the user enters the code again.
4. **Tests** cover the 20-wrong-code limit (HTTP 429), the `0600` file mode, replacement of a symlinked, loose-mode or foreign-owned file, `POC_SINGLE_USER` without `CODESPACES`, and session clearing on a public port.

## Consequences

- The code is still never printed by the console or returned in any response.
- A console started with only `POC_SINGLE_USER=1` outside a Codespace now requires sign-in like any other host.
