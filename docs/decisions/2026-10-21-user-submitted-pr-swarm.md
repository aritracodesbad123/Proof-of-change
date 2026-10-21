# A pull request a person submits runs with the advisory swarm on

**Date:** 2026-10-21
**Status:** accepted

## What changed

The advisory swarm is the step after the code verdict that labels findings, suggests notes, and writes a short summary. Those labels do not change the verdict.

A check that a person asks for now turns that step on.

- Request-a-check starts `ops/daily_run.py` with `--swarm`.
- The one command that starts the console in a GitHub Codespace sets `POC_SWARM=1` for that console. The console already passes `--swarm` on each check.
- The daily cap on requested checks stays 5.

A study run and a benchmark run still leave the swarm off unless that run asks with `--swarm` or with `POC_SWARM` set to `1`, `true`, `yes`, or `on`. This change does not set `POC_SWARM` for the whole machine, so a study started in another terminal is unchanged.

## Why

A pull request a person submits should get the same advice as a check started from the console. A study counts cost, so those extra calls stay off unless the study asks for them.

## Decision

1. The request worker's check command includes `--swarm`.
2. The Codespace start command sets `POC_SWARM=1` only on the console process it launches.
3. Study runs and benchmark runs keep the default off.
4. The request-a-check daily cap stays 5.

## Alternatives and tradeoffs

Setting `POC_SWARM` for every process in the Codespace would also turn the swarm on for a study run typed in that same Codespace. Limiting it to the console process avoids that. Leaving requested checks off would make a judge's check quieter than the console, and the summary would be missing.

## What it means for you

A check you request, or a check you run from the console that a Codespace starts, includes the advisory labels and the plain-language summary when a model is available. A study run or a benchmark run still skips that step until you ask. Requested checks still stop after five in a day.
