# A rejected provider key stops the run

## What changed

A run that is set to use Nebius already stopped when `NEBIUS_API_KEY` was missing or empty. It now also checks that the provider accepts the key.

Before any case starts, the run makes one cheap authenticated call (the models list). If the provider answers HTTP 401 or 403, the run stops at once with a short message. The message names the HTTP status and the variable, and it never prints the key.

If a 401 or 403 arrives later, during a case, the run stops there. Later cases do not start, and that failure is not written down as an ordinary `could_not_verify`.

In a benchmark or study run, a record whose AI calls all failed, or whose `model_provider_used` is `none`, is marked invalid. The verdict on that record is left as it is. The study scorer and the swarm scorer refuse the record, so it is not counted as `could_not_verify`. A record that simply does not have `model_provider_used` is still scored, so older result files keep working.

A models-list failure that is not HTTP 401 or 403 does not stop the run at startup. A later 401 or 403 still does.

## Why

A key the provider rejects used to run all the way to the end. Every model call failed, the record said `model_provider_used` was `none`, and the verdict was `could_not_verify`. That looks like a normal case the tool could not check. It was not. The AI never ran, and a score would have counted the miss as an abstention.

## Decision

- Before the first case, call the provider once with the key. HTTP 401 or 403 means do not start.
- If HTTP 401 or 403 arrives during a case, stop the whole run. Do not keep going, and do not save that case as `could_not_verify`.
- Say what happened in plain language. Never print the key.
- In a benchmark or study run, mark a record invalid when every AI call failed or when `model_provider_used` is `none`. Do not change the verdict.
- The study scorer and the swarm scorer refuse an invalid record, a record whose `model_provider_used` is `none`, and a record whose AI calls all failed. They do not count it as `could_not_verify`.
- An explicit `--model-provider none` is still the way to run with the AI off. In a benchmark or study run those records are invalid and are not scored.

## Alternatives and tradeoffs

Treating a rejected key like any other model error would keep the old behaviour: the run finishes and the score treats the case as "could not verify". That hides a broken key inside the abstention rate.

Stopping only at startup would miss a key that is revoked while the run is going. Stopping on a mid-run 401 or 403 drops the cases that have not started yet. That is the point: those cases would not be real model results.

Marking the record invalid, and refusing it in the scorer, keeps the verdict function unchanged. The bad record is still on disk, with the verdict the code produced, and it is kept out of the score.

## What it means for you

Set `NEBIUS_API_KEY` to a key the provider accepts. If the provider refuses it, the run stops and tells you the HTTP status. Nothing in that message is the key. Pass `--model-provider none` only when you mean to run with the AI off. Those benchmark records are not scored.
