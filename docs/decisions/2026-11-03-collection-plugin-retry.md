# Turn off a third-party pytest plugin that breaks collection on both sides

## What changed

When test collection fails the same way on the main side and the pull-request side, and the traceback is inside a
third-party pytest plugin, the check reads that plugin's entry-point name and runs the tests once more on both sides
with the plugin turned off (`-p no:<name>`). The run report says, in plain words, which plugin was turned off and
why. If the second run still collects nothing, the first result is kept. The same flags are passed to the coverage
run, which is another pytest start. How a verdict is chosen is unchanged.

## Why

urllib3 pull requests 5278 and 5352 failed while collecting tests on both sides. The error was
`module 'pytest' has no attribute 'pyodide_options_stack'`. A dev extra had installed pytest-pyodide, and pytest
loaded that plugin automatically. The crash was the same on both sides, so it was not a difference the pull request
introduced. The existing startup repair did not apply: that repair only runs when pytest stops with an internal
error before collection, and it leaves a plugin in place when the project's own files name it.

## Decision

- The rule is generic. No repository name and no plugin name is written into the code.
- Both sides must fail collection, with the same exception line and the same frames inside a third-party plugin
  (a file under site-packages that is not pytest itself). A side that already ran tests is left alone. A traceback
  that stays in the project's own files is left alone.
- The entry-point name comes from the traceback module matched to the installed pytest plugins (the pytest11
  entry points). If the module does not match, the distribution name is used. The flag is `-p no:<entry point>`,
  not the distribution name.
- One retry, on both sides. The coverage run uses the same flags when that retry is the result that is kept.
- If the retry still does not collect tests, the logs and the results from the first run are put back.
- The report sentence is recorded on the run. It does not feed the verdict.

## Alternatives and tradeoffs

- Leaving the failure as it was keeps the check at could not verify whenever a dev extra pulls in a plugin that
  cannot run here. The tests that do not need that plugin never get a chance to run.
- Turning off every installed plugin would also turn off a plugin the project needs. Only the plugin named by the
  traceback is turned off.
- Hardcoding one plugin would fix the two urllib3 runs and miss the next plugin that fails the same way.
- Retrying more than once would keep going after the plugin was not the cause. One retry is enough, and a failed
  retry keeps the original result.

## What it means for you

A check whose tests cannot be collected, with the same traceback on both sides pointing into a third-party pytest
plugin, runs the tests again with that plugin turned off. The run report says so. If that second run still cannot
collect tests, you see the original failure. The verdict is still the one the usual rules produce from whatever
results were kept.

## Offline proof

`tests/fixtures/collection_plugin/` is a pair of pytest logs: the same collection error, with the side folder name
as the only difference, and the traceback inside a third-party plugin. `tests/test_collection_plugin_retry.py`
checks that the entry-point name comes from the traceback and the installed metadata, that a different error, a
project file, or a side that already ran tests is not retried, that a failed retry keeps the first logs, and that
the report states the plugin was turned off. Nothing from those pull requests is run again.
