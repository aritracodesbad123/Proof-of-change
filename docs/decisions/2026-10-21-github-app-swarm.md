# The GitHub App runs a check with the advisory swarm on

**Date:** 2026-10-21
**Status:** accepted

## What changed

A check started by the GitHub App now passes `--swarm` to the runner. The advisory swarm is the step after the code verdict that labels findings, suggests notes, and writes a short summary. Those labels do not change the verdict.

The operator console already turns that step on itself. A command-line run, a study run, and a benchmark run still leave it off unless the run asks with `--swarm` or with `POC_SWARM` set to `1`, `true`, `yes`, or `on`.

A requested check (request-a-check) already runs with `--swarm` on main, so every check started for a user pull request now has the swarm on. The request-a-check daily cap stays 5.

## Why

A check that a person starts from a pull request through the App should show the same advice as a check started from the console. A study run and a benchmark run count cost and must not spend those extra calls unless the run asks.

## Decision

1. The GitHub App adds `--swarm` to the arguments of every check it starts.
2. It does not set `POC_SWARM` in the process environment, so a later study or benchmark run in the same process is not turned on by accident.
3. Study runs, benchmark runs, and command-line runs stay off unless they ask.
4. Request-a-check keeps its existing `--swarm` and its daily cap of 5.
5. The App's arguments come from one helper, so the swarm switch and the related-reports flag are set in one place.

## Alternatives and tradeoffs

Setting `POC_SWARM` in the environment would also turn the swarm on, but it would leak into anything else that process starts. Leaving the App off would make a pull-request check quieter than the console, and the summary would be missing. Turning the swarm on for every study run would spend the extra calls on the whole study.

## What it means for you

A check the GitHub App runs includes the advisory labels and the plain-language summary when a model is available. A study run, a benchmark run, or a command you start yourself still skips that step until you ask for it. A requested check also includes them. Request-a-check still stops after 5 checks in a day.
