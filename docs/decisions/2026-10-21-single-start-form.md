# One start form and one Run check button in the console

**Date:** 2026-10-21
**Status:** accepted

## What changed

The console's start page is one form: pull request link, optional Nebius API key, optional Nebius project ID, optional Tavily key, and the human-review option (on by default). One **Run check** button sends all of it in a single request. The separate "Save key" buttons are gone.

Keys typed into the form are kept in the browser tab's session storage, so they survive a page refresh and clear when the tab closes. They are never put in local storage or cookies. The server keeps them in memory for the session, as before. They are not written to disk, logs, reports, or replies, and they are not passed to pull-request code. A blank field keeps the value already sent this session.

When a console runs without sign-in (single-user mode in a Codespace), every request uses the one in-memory slot for that console, even if the browser sends an old or changed cookie. A refresh no longer moves the keys to a different slot.

When a check cannot start, the reply says why in plain words and the form shows it next to the button. A refused start because no sandbox can run says what to add, for example "No sandbox available: add your Nebius project ID".

The Nebius key and project ID typed into the form are the same values the Contree routing reads. When both are given and Contree can start, the check runs in Contree only, even where bubblewrap cannot start. When both are given but Contree still cannot start, the reason says so and does not ask for them again.

## Why

In a real Codespace test, a person saved the key with its own button, the page refreshed, and then Run check appeared to do nothing. Three buttons for three fields were confusing. Each key form was nested inside the start form, so a save also triggered the start handler. Start errors appeared only in a banner at the top of the page, so a refused start looked like silence.

## Decision

1. One form, one submit, one request to start a check.
2. Keys live in the tab's session storage and the server's memory only.
3. The single-user console uses one fixed session slot for keys.
4. Every failed start shows a plain reason on the form. Nothing fails silently.

## Alternatives and tradeoffs

Keeping the keys only on the server, tied to a cookie, is lost when the cookie changes. Local storage or a cookie would keep keys after the tab closes, which is longer than needed. Session storage is readable by scripts on the same page; the console loads no third-party scripts, and the tab is the user's own.
