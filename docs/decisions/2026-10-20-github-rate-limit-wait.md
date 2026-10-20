# A GitHub rate limit waits and retries

## What changed

When GitHub answers a read with status 403 or 429 and the remaining budget is 0, the run waits until the reset time and tries that read once more. The wait is capped (15 minutes unless configured otherwise) and is written to the log. The host token is read from GITHUB_TOKEN, then GITHUB_POC_TOKEN, then GH_TOKEN. That token is used only for API reads. It is not placed in the environment that runs pull-request code.

## Why

Hitting the limit used to skip the whole library for the day. A short wait is enough for the budget to refill, and skipping dropped work that could have been read a few minutes later.

## Decision

Wait only when the remaining budget is exactly 0. If the reset is further away than the cap, do not wait, and say so in the log. Any other 403 is still an error. Retry the read once after a wait that fits the cap.

## Alternatives and tradeoffs

- Keep skipping the library. That loses the day's reads whenever the shared address is out of budget.
- Wait with no cap. A long reset would stall the run.

## What it means for you

Set a read-only token on the host if you have one. A used-up budget pauses until reset, within the cap, and then retries. Pull-request code still cannot see the token.
