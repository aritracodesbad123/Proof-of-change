# A setup repair does not set the verdict

## What changed

The notes on the setup-repair functions now say what a repair does. It looks up a setup or import failure,
installs the same fix on both sides, and runs the check again, up to 3 logged tries. The verdict after that
run comes from the same rules as any other run. A failure the pull request caused is not retried, and the
repair does not install operating-system packages.

## Why

The old note said this step could move a could-not-verify result to verified. That described the repair as
choosing the verdict. The repair only makes it possible to run the check. The tests and the usual rules
decide the result.

## Decision

Leave the repair behavior as it is. Change the description so it matches that behavior. A fresh probe
line-coverage measurement still runs only when the change is small. A larger change skips it, and the
verdict stays could not verify.

## Alternatives and tradeoffs

The old note could have stayed. Readers would still be told that the repair itself moves the verdict.
Rewriting the note does not change who can be verified, or how many tries a repair gets.

## What it means for you

A setup or import failure can still be looked up and installed on both sides, then run again. The report
shows the same verdict names as a check that did not need a repair. Nothing new has to be configured.
