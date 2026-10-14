# The daily run needs an AI model when the AI-probe rule is on

## What changed

- A run now uses the AI model (Nemotron on Nebius) by default. Before, it used no model unless asked.
- If the daily run's mode only allows "verified" when an AI-written probe ran a changed line (the default "full"
  mode), and no model is available (for example the key is missing), the run stops before testing anything and
  says why in plain words. Picking PRs, rebuilding a report, or benchmark mode still works without a model.
  Passing a model, or choosing a mode without that rule (including an explicit "none"), also runs.

## Why

On 14 Oct the daily run was started without asking for the model. The key was set, but the run never used it,
because "no model" was the default. The rule added the day before says a PR is only "verified" when an
AI-written probe ran the changed code. With no model there are no such probes, so all 23 PRs came out as
"could not verify", including 11 clean ones. A run like that wastes over an hour and tells us nothing.

## Trade-offs

- A run with a missing or broken key now produces nothing instead of a weak result. That is on purpose: a loud
  stop is easier to notice and fix than a quiet wall of "could not verify".
- Runs that should not use a model can still choose a mode without the AI-probe rule.
- Benchmark mode is not stopped by this check. A benchmark that keeps the default "full" mode and has no model
  can still come out "could not verify" for each case, instead of stopping first.
