# Behavioural probes run with the project's own test settings

Date: 2026-10-22

## Decision

On product checks, behavioural probes now get the same test settings the project's own pytest runs get. The settings are read from the main side's checkout only, as files, and the identical values are applied to both sides. Only the Python path entries are joined to each side's own checkout.

1. The first pytest config file pytest would use: `pytest.ini`, `pyproject.toml` (`[tool.pytest.ini_options]`), `tox.ini` (`[pytest]`) or `setup.cfg` (`[tool:pytest]`).
2. From it: pytest-env `env` entries (with the `D:` default-only and `R:` raw prefixes), the pytest-django `DJANGO_SETTINGS_MODULE` key or `--ds` in `addopts`, and `pythonpath` entries inside the checkout.
3. Plain literal environment assignments at the top level of the root `conftest.py`. The file is parsed, never run.

Nothing is specific to one repository. A project's config cannot set variables that steer the runner, the interpreter or the sandbox: `PATH`, `HOME`, `TMPDIR`, `SHELL`, `USER`, and every variable starting with `PYTHON`, `LD_`, `COVERAGE_` or `PYTEST_`.

Local probe runs, probe coverage runs and Contree probe runs get the same settings. Contree runs also get the Python path entries, under the remote checkout.

Each run's record keeps the settings source file and the variable names, never their values. If the pull request changes a pytest config file, the root `conftest.py` or the Django settings module's files, the report flags it, because the probes used main's settings rather than the PR's.

Study runs and the daily study are unchanged: they get no project settings, and their probe output has the same shape as before.

## Why

On a Django app, every probe crashed on the main side because it loaded production settings. The app refused to start without its test flags, so the probe could not count, even though the project's tests ran fine with their pytest config.

## Empty AI-written probes

An AI-written probe whose code has no test statements (only imports, comments, a docstring or `pass`) is now rejected when it is written, as an "empty probe". The model is asked once more, with that reason. If the second answer is empty too, no probe file is written. Before, such a probe ran, printed nothing, and was counted as a crash on every run.
