# Each person sees only their own checks

**Date:** 2026-10-20
**Status:** accepted

## What changed

The operator console now has sign-up, sign-in, and sign-out. A signed-in person sees and can open only the checks their account started. One admin can see every check, including older checks that were never tied to an account. Signing up can be turned off, and an invite code can be required.

## Why

The console listed every check on the machine. On a shared demo, that shows one person’s pull request to everyone else.

## Decision

Keep accounts in a small SQLite file and sessions in an HttpOnly cookie. The cookie is tied to a secret from the environment, not a password written into the program. Passwords are stored only as salted scrypt hashes. Forms send a second token so another site cannot submit them. Five wrong passwords lock that account for a while.

The check record itself is unchanged. The console writes the account id beside the run. Every console address that returns a run, a log, a PDF, or the behaviour map checks that id on the server. Someone else’s check looks the same as a missing one.

The first admin is an email in the environment, or a one-time command that marks an account that already exists. Neither path puts a password in the environment or on the command line.

Command-line checks, benchmarks, and study runs do not sign in and do not change.

## Alternatives and tradeoffs

Hiding other people’s checks only in the page would still leave the addresses open. A hosted database would survive a free host wiping its disk, and it would add a service this demo does not have. The SQLite file is small enough for Render, and it disappears when a free instance sleeps, so accounts there are temporary unless the disk is kept.

## What it means for you

Set a long `POC_SESSION_SECRET` before anyone can sign in. Optionally set the admin email, turn sign-up off, or require an invite code. After you sign in, My runs lists only your checks. Sign out from the header when you are done.
