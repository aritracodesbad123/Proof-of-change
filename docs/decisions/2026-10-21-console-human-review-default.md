# Human review is the default step for a console check

**Date:** 2026-10-21
**Status:** accepted

## What changed

A check a person starts in the operator console now follows this flow by default:

1. The AI drafts behaviour probes for the pull request.
2. **Human review:** the person keeps or drops each drafted probe and can add up to 20 of their own test ideas. Nothing runs until they continue.
3. The approved probes and the project tests run, and the code publishes the verdict.

The review option on the start form is ticked by default, and the API treats a console check that does not say otherwise as review on. The person can untick it to skip the review for that one check. The default lives in the console's own per-check settings. No machine-wide environment variable turns it on or off, so `POC_CONSOLE_APPROVAL` no longer has any effect.

The process chart and the timeline show **Human review** as its own step between the AI probes and running them. It shows as skipped when a check did not use it.

## What the review records and how it affects the verdict

- The record (`record.json`) now has a `human_review` section: which AI probes were kept and which were dropped, the test ideas the person added, the probes written from those ideas, and any claim left with no probe.
- Probes written from a person's test ideas are labelled **human-requested** in the record and in both reports (the PR report and the reviewer report), which also gain a "Human review" section.
- If the review leaves a claim with no probe, for example because the person dropped the only probe for it, a verified result is capped at could_not_verify. The cap only lowers a verified result and is applied after the normal verdict rules, which are otherwise unchanged. Without it, dropping the probe for a false claim could have produced verified.
- Each test idea is limited to 500 characters and the whole review to 64 KB.
- The review step has a **Cancel check** button. A cancelled check stops before any probe runs and says "review cancelled".
- A check that waits too long for a review fails with "review not completed".
- The console uses one term, "test ideas", for what the person adds.

The fixed benchmark suite stays a CI job. It is not a step of each check.

## What stays automatic

Study runs, daily study runs, benchmark runs and command-line runs never pause for a person. They still refuse to start if `POC_HITL` is set.

The GitHub App and request-a-check also stay automatic, because no person is there to answer. Neither passes `--console-job`, and a requested check now removes every review switch from its child environment, so it cannot pause even on a host where the console has review on. Tests cover both routes.

The verdict logic is unchanged. Review only decides which probes run.

## Why

The person who starts a check from the console knows what the change is meant to do. Letting them prune the AI's probes and add their own ideas before anything runs gives better probes, and it makes the human step visible instead of a hidden option.

## Alternatives and tradeoffs

Turning review on with an environment variable would affect every route on that machine, including the App and requested checks, which would then wait for nobody. Letting the reviewer rewrite probe code was left out: keep or drop plus free-text ideas covers the need without a code editor in the console. A review step adds waiting time to a console check, so the person can still skip it.

## What it means for you

When you run a check in the console, it stops after the AI drafts probes and asks you to review them. Untick the review option before you start if you want it to run straight through.
