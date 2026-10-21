# A Codespace opens the console without sign-in, and only while its port stays private

**Date:** 2026-10-21
**Status:** accepted

## What changed

A Codespace (`CODESPACES=true`) and a console started with `POC_SINGLE_USER=1` do not ask for an account. Email, Google, and GitHub sign-in are not configured there, and the machine belongs to one person. Every other host still requires sign-in.

Port 8787 is private in the dev container. The start script reads `gh codespace ports` when that command is available. If port 8787 is public, the console does not start, and sign-in is not skipped. The message tells the person to set the port back to private.

A request issue is public. The template and the README say not to paste an email address, a key, or any private information. The setup notes name three labels: `request-a-check`, `request-running`, and `request-done`.

## Why

Judges opening a Codespace have no way to finish email or provider sign-in. Skipping it on a public port would leave the console open to anyone who has the link. A request issue is readable by the world, so a pasted key or email address would be public too.

## Decision

1. Skip sign-in only when `CODESPACES` is true, or when `POC_SINGLE_USER` is set on the console process. Do not skip it on any other host.
2. Keep port 8787 private. If a visibility check says that port is public, do not start the console and do not skip sign-in.
3. Tell people, on the request form and in the README, not to paste an email address, a key, or private information. The issue is public.
4. Document `request-running` next to `request-a-check` and `request-done`.

## Alternatives and tradeoffs

Leaving sign-in on in a Codespace would stop a judge at a form that cannot send mail. Skipping it on every host would expose a shared console. Checking the port at start, and again before a request is treated as signed in, keeps the shortcut limited to a private Codespace.

## What it means for you

Open a Codespace and use port 8787. Do not make that port public. If you do, set it back to private and start the console again. On any other host, sign in as usual. When you request a check, paste only the public pull request link. Create the three labels `request-a-check`, `request-running`, and `request-done`.
