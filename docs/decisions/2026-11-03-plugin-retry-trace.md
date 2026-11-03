# The plugin retry writes down what it tried

## What changed

When the check retries pytest with a third-party plugin turned off, the record and the run report now say what
happened. They say whether the failure was recognised, which plugin was chosen, whether the installed plugin list
could be read (and why not, when it could not), the exact `-p no:<name>` flags, and the outcome. A retry that
works says so. A retry that fails again keeps the first result and quotes the new first error line on each side.
The retry's own pytest output is kept as `pytest-main-retry.log` and `pytest-pr-retry.log` next to the record.
There is still one retry, with every chosen plugin on that one command.

## Why

pytest pull request 15324 matched the offline check: the same startup error in a third-party plugin on both sides,
resolved to the entry point `asyncio`. The live record had an empty plugin list and no report line. Reading the
plugins from the run environments had failed, and that failure was thrown away. A retry that failed again also
replaced its logs with the first run, so there was nothing left to read.

## Decision

- Write one `plugin_retry` object on the record whenever the failure is recognised, and the same facts in one
  plain sentence on the run report. This does not choose a verdict.
- If the plugin list cannot be read, store the reason and do not retry. Do not leave the record blank.
- If the retry fails again, put the first logs back for the verdict and keep the retry logs under the names above.
- One retry. Do not try plugins one by one.

## Alternatives and tradeoffs

- Saving the trace only in the pytest log would still leave `record.json` blank, which is what hid this run.
- Retrying once per plugin would multiply the test time and could turn off a plugin that was not the cause.
  One command with the chosen flags is enough.

## What it means for you

A check that hits this retry now says, in the record and the report, whether it ran and how it ended. If the
plugin list could not be read, the report says why. The retry logs stay next to the other pytest logs. The
verdict is still chosen by the same rules as before.

## Offline proof

`tests/test_collection_plugin_retry.py` checks a retry that works, a retry that fails again (the first result
stays, the retry log is kept), and a plugin list that cannot be read (recorded, and pytest is not run again).
Nothing from the pull request is run again.
