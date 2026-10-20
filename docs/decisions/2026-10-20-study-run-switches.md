# Study runs can leave the advisory swarm and operator approval off

## What changed

Command-line runs and benchmark runs leave the advisory model swarm off unless the run asks for it.
Ask with the `--swarm` flag, or by setting `POC_SWARM` to `1` (also `true`, `yes`, or `on`). When the swarm
is off, the run makes no swarm model calls at all. The operator console still asks for the swarm, and it
turns that switch on itself.

Every result now carries four fields.

- `swarm_requested` is true when the run asked for the swarm, from `--swarm` or `POC_SWARM`.
- `swarm` is `on` only when that step actually ran, and `off` when it did not.
- `operator_approval_requested` is true when `POC_HITL` is set.
- `operator_approval` is `on` only when that approval step was entered, and `off` when it was not.

Asking for the swarm and then skipping it still records the request. That happens when there is no model,
when `--no-probes` is set, or when the baseline does not use probes. Setting `POC_HITL` without the
approval step being reached records the request as true and the step as off.

A command-line run or a benchmark run stops immediately, with a short explanation, if `POC_HITL` is set.
No environment variable waives that stop. The operator console starts one pull-request check with
the `--console-job` flag. That flag is the only way such a check may start while operator approval
is on. A benchmark run still stops if operator approval is on, even with the flag. The result still
says operator approval was requested, so a study score still refuses it.

Swarm model calls are listed on their own line, `cost.swarm`, and are not added into the main cost of the
pull request. The headline totals stay comparable with the cost figures in section 7.10 of the paper.

The study scorer refuses a folder of results when any of the four fields is true or missing. It stops
with a short message and does not print a score.

A benchmark run that asks for the swarm writes its results in a separate folder whose name ends in
`-swarm-on`. The main study scorer does not read that folder. A separate swarm scorer reads it, and it
accepts a record only when the swarm was requested and the swarm step ran. The main scorer still refuses
a swarm-on record if one is placed in the main folder.

## Why

The study has to measure the same work the paper measured. Recording only whether a step ran hid a run
that had the switch on and then skipped the step. That run could be scored as if the switch had been off.
Operator approval can add or drop probes. A marker that let a command-line or study run start with
approval on would change the result.

## Decision

- Swarm off is the default for command-line and benchmark runs. The console turns it on explicitly.
- Operator approval cannot be switched on for a command-line or benchmark run. If `POC_HITL` is set, the run refuses to start. The console's single pull-request check passes `--console-job` and may start; nothing in the environment can do that, and a benchmark run still refuses.
- Record the request and what ran, for both the swarm and operator approval, on every result.
- Do not score a study folder unless every record has all four fields and none of them is true.
- Put swarm-on study results in their own labelled folder and score them on their own path.
- Keep swarm spend out of the main per-pull-request total.

## Alternatives and tradeoffs

- Record only what ran. A skipped swarm would look the same as a swarm that was never requested, and the
  study scorer would accept it. Recording the request as well makes that visible.
- Let an environment variable start a check that has operator approval on. Anyone could set that
  variable and change which probes run. The console passes a flag instead, and a benchmark run
  ignores the flag.
- Score swarm-on results in the same folder as the main study. The main scorer would have to skip some
  files and could pick one up by mistake. A separate folder keeps the two sets apart.
- Leave the swarm on and subtract its cost afterwards. That still spends the calls, and a missed
  subtraction would inflate the study. Not calling the models is clearer.
- Fold swarm spend into the main total and footnote it. The headline number would no longer match section
  7.10 of the paper.

## What it means for you

A normal check or a benchmark run does not call the advisory swarm and does not pause for approval. Pass
`--swarm`, or set `POC_SWARM=1`, when you want the advisory labels and the plain-language summary. The
operator console's own check passes `--console-job`, so it can pause for approval. That result still says
operator approval was requested, and a study score refuses it. On the result, `swarm_requested` says
whether you asked, and `swarm` says whether the step ran. The same pair for operator approval is
`operator_approval_requested` and `operator_approval`. A study score only includes records where all four
say the switches were off. Swarm-on benchmark results are in the folder whose name ends with `-swarm-on`,
and they are scored on their own by checking every record, not the folder name. Read swarm spend under
`cost.swarm`, not in the main total.
