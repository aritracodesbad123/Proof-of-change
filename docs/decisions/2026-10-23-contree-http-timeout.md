# A slow Contree poll must not cancel the sandbox

**Date:** 2026-10-23
**Status:** accepted

## What changed

- The Contree client now allows 120 seconds for one HTTP call. The SDK's own default is 10 seconds. That limit applies to a single poll or upload, not to the whole install or test step.
- A dropped HTTP connection (`ContreeTransportError`) is treated like a timeout for the existing product-check retry: at most 3 tries, and only before Contree has created the run. Once the run exists, a transport error is final, same as a timeout. A refused login is still not retried.
- On a product check, a Contree error that escapes the check is written as could not verify, with the same refusal as a prepare failure. The check no longer exits with a harness error and no record. Study runs, bench mode, and the daily study still record a harness error and do not retry.

## Why

Live product checks were ending because one Contree HTTP call took longer than 10 seconds. The SDK then cancelled the sandbox. A prepare failure became could not verify. The same error later in the check became a harness error with no verdict file.

## Decision

- Raise the HTTP timeout on our client. Do not pass the Nebius key into that client; the SDK keeps reading it from the environment.
- Do not retry a run after Contree has created it. The SDK cancels that run, and a second try could run pull-request code twice.
- A product check that loses Contree still ends as could not verify. It does not run the pull request locally, and it does not become verified.

## Alternatives and tradeoffs

- Leaving the 10 second default keeps failing checks that are only slow.
- Retrying after the run exists would risk running the pull request twice.
- A missing record looks like a crash. Writing could not verify says the check did not finish, which is the honest result.

## What it means for you

A product check is less likely to stop because one Contree poll was slow. If Contree is really down, the result is still could not verify, and nothing from the pull request runs on your machine.
