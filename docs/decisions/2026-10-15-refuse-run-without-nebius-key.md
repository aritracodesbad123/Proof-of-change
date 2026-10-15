# A run must not start with the AI turned off

## What changed

A daily run, and an eval run that is set to use Nebius, now checks the Nebius API key before it does any work.
The variable is `NEBIUS_API_KEY`, the same one the model code already reads. If it is missing or empty, the run
stops at once with a non-zero exit and a short message that names the variable and how to set it. The message
never prints the key.

Passing `--model-provider none` is the way to run with the AI off. The result record then says the AI was off.

Every result record now has `model_provider_used`. That field is the provider that actually completed a call,
such as `nebius` or `none`, not the provider the run was asked to use. If a call was skipped or failed, the
record also has `model_provider_fallback` saying so.

## Why

An earlier run went ahead with the AI off and still looked successful. The key was missing, so the tool quietly
used only the hand-written probes and wrote a normal-looking result. A person reading that result could not
tell that the model had never been called.

## Decision

- Stop before starting when the run is set to Nebius and `NEBIUS_API_KEY` is missing or empty. Do not fall back
  and keep going.
- Allow a run with no key only when the provider is an explicit `none`. Say in the record that the AI was off.
- Recorded answers (saved test fixtures) do not call Nebius, so they do not need this key. They stay labelled
  as fixtures.
- On each result, store the provider that completed a call. If the baseline does not use model probes, if probes
  were switched off, or if a call failed, write that down too.

## Alternatives and tradeoffs

- Keep going with the hand-written probes and only add a warning. That is what the tool used to do. A warning
  in a long log is easy to miss, and the result still looks finished. Stopping is louder, and it means a run
  with a missing key produces nothing until the key is set.
- Treat an empty key the same as a missing one. A blank value is not a key, and printing it would not help.
- Require the key even for `--model-provider none`. That would make an intentional no-AI run impossible. The
  explicit flag is the off switch, and the record has to say so.
- Guess the provider from the flag the person passed. That flag is what they asked for, not what ran. A skipped
  or failed call would still look like Nebius. The new field is filled from calls that succeeded.

## What it means for you

Set `NEBIUS_API_KEY` before a daily run or an eval that uses Nebius (that is the default). If you want a run
with the AI off, pass `--model-provider none`. After a run, read `model_provider_used` on the result. If it is
`none`, the model did not complete a call, and `model_provider_fallback` says why.
