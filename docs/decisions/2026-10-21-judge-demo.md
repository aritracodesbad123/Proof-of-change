# A free page and a request path for judges

**Date:** 2026-10-21
**Status:** accepted

## What changed

Judges get three ways to look at Proof-of-Change without paying for a host.

The main link is a results page on GitHub Pages. It is the same console (light background, the flow chart, and the report) showing finished checks that are already stored with the project. Opening that page does not install a library and does not call an API.

A judge can also open a GitHub issue with the "Request a check" template and paste one public pull request link for a Python library. A worker on our own Linux machine takes those issues one at a time, runs the normal sandboxed check, and comments with the verdict and a report link. GitHub emails the person who opened the issue. The worker does not start between 10:40 and 12:30 IST, stops after a daily limit (five, unless changed), and waits when a study run has marked the machine as busy. If the worker has not checked in recently, a small GitHub Action says the checker is offline and points at the results page.

A GitHub Codespace can start the console on Linux. A judge may paste a Nebius key into a password field. That key stays in the server's memory for the sign-in. It is not written to disk, logs, reports, or replies. Without a key, a live check uses the recorded AI answers. If bubblewrap cannot start and Contree is not set up, the console refuses to run pull-request code. The only opt-in is the environment variable `POC_UNSAFE_NO_SANDBOX=1`, and the page shows a warning. The vetted sample still plays back without running that code.

The console's operator-approval step is off unless a person ticks it for that check, or `POC_CONSOLE_APPROVAL` is set. A study run still refuses to start when `POC_HITL` is set.

A `/prove` comment starts a check only when it is on a pull request. The same comment on a plain issue is ignored.

## Why

The judging window is 1–15 December, and the rules ask for a working demo link that judges can use for free. A live check is too heavy and too secret-sensitive to run inside a public web page. Judges still need to see real verdicts, and they need a way to ask for a check or try the console.

## Decision

1. Publish a static replay of finished checks. Do not recompute verdicts for that page.
2. Accept new checks only through the issue template, and only on the project machine, with the quiet hours, the daily cap, and the study lock.
3. Keep a pasted key in process memory for that sign-in. Never print it or put it in a comment.
4. Do not fall back to an unsandboxed run. Contree or bubblewrap, or no pull-request code, unless `POC_UNSAFE_NO_SANDBOX=1` is set on purpose. That choice shows a warning.
5. Leave operator approval off for a console check unless that check, or `POC_CONSOLE_APPROVAL`, turns it on. Do not change the study rule that refuses `POC_HITL`.
6. Ignore `/prove` on a plain issue. React only when the comment is on a pull request.

## Alternatives and tradeoffs

A always-on paid server would run checks the moment a judge asked. It costs money and would hold keys on a public host. The results page is instant and free; a new check waits for the project machine and for the quiet hours. A Codespace is free for the judge and is Linux, which live checks need, but it is slower to start than the results page.

## What it means for you

Use the results page to read finished checks. Open a "Request a check" issue for a new public Python pull request, and wait for the email. Do not put an email address, a key, or other private information in that issue. Or open a Codespace, use port 8787, and paste a key only if you want a live model call. Leave that port private. Live checks need Linux. Turn on GitHub Pages from the Actions source so the results link is served, and create the labels `request-a-check`, `request-running`, and `request-done`.
