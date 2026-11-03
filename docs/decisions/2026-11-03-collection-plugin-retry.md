# Turn off a third-party pytest plugin that breaks collection on both sides

## What changed

When test collection fails the same way on the main side and the pull-request side, and the traceback is inside a
third-party pytest plugin, the check reads that plugin's entry-point name and runs the tests once more on both sides
with the plugin turned off (`-p no:<name>`). The same retry also runs when pytest stops at startup with an internal
error raised in a third-party plugin's `pytest_configure`, including a warning (a name ending in Warning) printed on
an `INTERNALERROR>` line. The plugin is left on when the project's own pytest config names it, in `addopts` / `-p` or
in `required_plugins`, in `pyproject.toml`, `pytest.ini`, `tox.ini`, or `setup.cfg`. The run report says, in plain
words, which plugin was turned off and why. If the second run still produces no test results, the first result is
kept. The same flags are passed to the coverage run, which is another pytest start. How a verdict is chosen is
unchanged.

## Why

urllib3 pull requests 5278 and 5352 failed while collecting tests on both sides. The error was
`module 'pytest' has no attribute 'pyodide_options_stack'`. A dev extra had installed pytest-pyodide, and pytest
loaded that plugin automatically. The crash was the same on both sides, so it was not a difference the pull request
introduced. The in-command startup repair did not see this pair of logs: it runs inside one Contree pytest command
when that command exits 3, and it does not compare the two sides. pytest pull request 15324 then died at startup
in a third-party plugin's `pytest_configure`, on an `INTERNALERROR>` line whose exception is a Warning
(`PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset`). That is not
a collection error, so the both-sides retry skipped it.

## Decision

- The rule is generic. No repository name and no plugin name is written into the code.
- Both sides must fail collection, with the same exception line and the same frames inside a third-party plugin
  (a file under site-packages that is not pytest itself). A side that already ran tests is left alone. A traceback
  that stays in the project's own files is left alone.
- The entry-point name comes from the traceback module matched to the installed pytest plugins (the pytest11
  entry points). If the module does not match, the distribution name is used. The flag is `-p no:<entry point>`,
  not the distribution name.
- A startup internal error is included when both sides show it, the frames meet in a third-party plugin's
  `pytest_configure`, and the exception line matches after side folder names are removed. `INTERNALERROR>` is
  removed before the line is read. A name ending in Warning counts, as well as Error and Exception.
- That startup retry does not turn a plugin off when either side's pytest config names it with `-p` or
  `required_plugins`. The name may be the entry point (`asyncio`) or the distribution that provides it
  (`pytest-asyncio`), read from the installed plugin metadata. Those names are compared in PEP 503 form:
  lowercase, with `-`, `_` and `.` treated as the same character. Listing the package as a dependency does
  not, by itself, count as naming it.
- One retry, on both sides. A log that already records the older in-command startup repair is not retried again.
  The coverage run uses the same flags when that retry is the result that is kept.
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

A check whose tests cannot be collected, or whose pytest stops at startup with the same internal error on both
sides inside a third-party plugin, runs the tests again with that plugin turned off. The run report says so. A
plugin the project's pytest config names with `-p` or `required_plugins` stays on. If that second run still cannot
produce test results, you see the original failure. The verdict is still the one the usual rules produce from
whatever results were kept.

## Offline proof

`tests/fixtures/collection_plugin/` is a pair of pytest logs: the same collection error, with the side folder name
as the only difference, and the traceback inside a third-party plugin. `tests/fixtures/startup_plugin/` is the
startup shape: `INTERNALERROR>` lines, `pytest_configure` in a third-party plugin, and a Warning. One config
names the entry point. Two more name the distribution, one in `required_plugins` and one with `-p`.
`tests/test_collection_plugin_retry.py` checks the entry
point, including `asyncio` for that startup log, that a named plugin is not retried, that a different error, a
project file, or a side that already ran tests is not retried, that a failed retry keeps the first logs, and that
the report states the plugin was turned off. Nothing from those pull requests is run again.
