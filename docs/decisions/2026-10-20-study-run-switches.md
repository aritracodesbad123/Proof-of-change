# Study runs can leave the advisory swarm and operator approval off

## What changed

Command-line runs and benchmark runs now leave the advisory model swarm off unless the run asks for it.
Ask with the `--swarm` flag, or by setting `POC_SWARM` to `1` (also `true`, `yes`, or `on`). When the swarm
is off, the run makes no swarm model calls at all. The operator console still runs the swarm, and it turns
that switch on itself.

Every result now says `swarm: on` or `swarm: off`.

The mid-check where a person approves probes, or adds scenarios, stays in the operator console only. A
command-line run or a benchmark run stops immediately, with a short explanation, if `POC_HITL` is set. It
does not ignore that setting and continue. Every result says `operator_approval: off` or
`operator_approval: on`.

Swarm model calls are listed on their own line, `cost.swarm`, and are not added into the main cost of the
pull request. The headline totals stay comparable with the cost figures in section 7.10 of the paper.

## Why

The study has to measure the same work the paper measured. The advisory swarm and the operator approval
step were added later. The swarm spends extra model calls. Operator approval can add or drop probes, which
changes the result. Leaving either of those on during a study run would make the numbers impossible to
compare.

## Decision

- Swarm off is the default for command-line and benchmark runs. The console turns it on explicitly.
- Operator approval cannot be switched on for those runs. If `POC_HITL` is set, the run refuses to start.
- Record both switches on every result.
- Keep swarm spend out of the main per-pull-request total.

## Alternatives and tradeoffs

- Leave the swarm on and subtract its cost afterwards. That still spends the calls, and a missed
  subtraction would inflate the study. Not calling the models is clearer.
- Quietly ignore `POC_HITL` on a study run. A person could think approval had run, or a leftover setting
  could change which probes run with no warning. Stopping is louder.
- Fold swarm spend into the main total and footnote it. The headline number would no longer match section
  7.10 of the paper.

## What it means for you

A normal check or a benchmark run does not call the advisory swarm and does not pause for approval. Pass
`--swarm`, or set `POC_SWARM=1`, when you want the advisory labels and the plain-language summary. Use the
operator console when you want to approve probes before they run. On the result, read `swarm` and
`operator_approval`. Read swarm spend under `cost.swarm`, not in the main total.
