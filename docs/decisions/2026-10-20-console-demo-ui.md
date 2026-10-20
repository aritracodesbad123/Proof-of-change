# The operator console is dressed for a demo

**Date:** 2026-10-20
**Status:** accepted

## What changed

The operator console — the page where you paste a pull-request link and watch a check — has a new look. It supports a dark theme and a light theme, a consistent set of type sizes, and colour-coded verdict badges for verified, needs attention, could not verify, and no code change. The accent colour is NVIDIA green.

The landing page shows the six stages a check moves through: fetch, sandbox, base versus pull-request tests, AI probes, coverage, and verdict. A live check fills that same timeline from the stages the checker already reports. Logs are split into sections you can open and close. The three-agent swarm is labelled advice only, and that advice does not change the verdict. The finished run has a behaviour map you can hover and expand, the reason in plain sentences, links to the evidence, and the cost and time already stored for that pull request. Past runs are cards you can filter, with a PDF download when a report file exists.

## Why

The console worked, but it looked like a rough internal page. A hackathon demo needs the same checks to be readable on a recording: what stage is running, what the verdict means, and that the agents are not the thing that decides.

## Decision

1. Keep the verdict, the probes, the swarm's behaviour, and the cost figures exactly as the checker records them. The page only formats those fields. It does not invent a verdict or add prices together when the record did not store a total.
2. Offer light and dark themes, remember the choice in the browser, and follow reduced-motion settings.
3. Show PDF links on past-run cards only when the report file is already on disk, using the same report lookup the run page already used.
4. Check the new presentation with front-end tests, and run those tests in continuous integration alongside the existing Python suite.

## Alternatives and tradeoffs

A new application framework would have meant a heavier build and a new way to host the page. The existing React build stays, so the free Render service still serves the same console. The timeline groups the checker's real stages into six labels; the full stage list is still one click away, because claims can be drafted before the tests finish and a single bar would hide that.

## What it means for you

Open the console, paste a pull-request URL, and watch the stages. Switch theme with the button in the header. The green, amber, grey, and blue badges are the checker's verdict, not a new one. Ultra, Lightning, and Super still only advise. Download the PDF from a past run when that run wrote one.
