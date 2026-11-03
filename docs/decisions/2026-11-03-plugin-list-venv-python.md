# Read installed pytest plugins with the interpreter the tests use

## What changed

When the check reads the installed pytest plugins, it uses the same interpreter the test command just ran
on that side. A local run and a bubblewrap run both use that side's `venv/bin/python`, and they run it
inside the same sandbox as pytest. A Contree run uses `python` in the checkpoint, the same program as
`python -m pytest`. The base-side pytest run uses that same interpreter. The check no longer decides the
interpreter is missing because the host does not see it as a regular file.

## Why

A real run recognised the same startup failure in a third-party plugin on both sides, then recorded that
the plugin list could not be read: each side had no Python interpreter, so the retry never ran. The tests
had just run with `venv-main/bin/python` and `venv-pr/bin/python`. Those paths are symlinks to the
interpreter the sandbox mounts. On the host the target is not a regular file, and a separate check stopped
there. The test command does not do that check. It runs the symlink, and the sandbox resolves it.

## Decision

- One helper names the interpreter. The timed pytest runs, the coverage pytest, the base-side run, and the
  plugin-list read all use it.
- Local and bubblewrap: `<venv>/bin/python`, executed in the side sandbox. Do not require the host to see
  a regular file.
- Contree: `python` in the checkpoint.
- If that program cannot be run, the record says why and the retry does not run. The verdict rules are
  unchanged. No repository is named in the code.

## Alternatives and tradeoffs

- Keeping the host file check would keep skipping a retry the test command can already run.
- Asking a different interpreter, such as whatever `python` is on the host, would list plugins pytest did
  not load.

## What it means for you

A check that stops at startup in a third-party plugin, the same way on both sides, can turn that plugin
off even when each side's Python is only a symlink the sandbox can run. The report still says whether the
plugin list was read. How a verdict is chosen is unchanged.

## Offline proof

The test builds a main venv and a pull-request venv whose `bin/python` is a symlink the host does not see
as a file. The plugin list is read by running that path, the retry runs, and the base-side pytest command
starts with the same path. A Contree read uses `python`, not the host symlink. Nothing from a live pull
request is run again.
