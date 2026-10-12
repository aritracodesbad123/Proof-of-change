# 2026-10-13: Normalize model probe ids from Nebius / Nemotron

## What changed

Model-written probes now accept ids such as `P1` or `Feature_Groups` by turning them into lowercase
slugs (`p1`, `feature-groups`) before validation. Path-like ids (`../x`) are still refused. The probe-writing
prompt asks the model for lowercase slug ids.

## Why

A live `--model-provider nebius` run on mlxtend#1229 called Nebius Token Factory successfully and extracted
grounded claims, but the generated probe was rejected with `bad probe id 'P1'`. Nemotron commonly returns
uppercase ids; the runner only allowed `[a-z0-9-]`. Without this change, live Nebius probes never land even
when the API call works.

## Decision

Normalize ids (lowercase, non-alphanumerics to hyphens, cap length) inside `validate_probe`, and keep rejecting
ids that look like paths. Tell the model in `PROBES_PROMPT` to use lowercase slugs.

## Alternatives and tradeoffs

- *Reject and retry the model* would spend more Token Factory credits and still fail if the model prefers `P1`.
- *Allow any printable id* would risk awkward filenames under `model-probes/`. Slugs stay safe for file names.

## What it means for you

Live Nebius / Nemotron probe ids like `P1` are kept. Re-run with `--model-provider nebius` to get model probes
in the record instead of only the rejection error.
