# Probe results may say crashed or rejected

## What changed

A probe result can now be recorded as crashed or rejected, and that record still validates. Crashed means the probe stopped on the main side. Rejected means the probe checked none of its own claims.

## Why

Those two words were already written onto probe results, but the shared record format did not list them. A record that used them failed validation, so a day's results looked incomplete even when the run itself had finished.

## Decision

Add crashed and rejected to the allowed probe status and to the allowed status of each probe. Nothing new is required. Older records stay valid.

## Alternatives and tradeoffs

- Keep the words out of the format and drop them before saving. That would hide a real outcome.
- Invent a new required field. That would make older records invalid.

## What it means for you

A probe that crashed or was rejected is a valid result. You can read that status in the record. This does not change how a verdict is chosen.
