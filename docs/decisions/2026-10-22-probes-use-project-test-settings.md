# Behavioural probes run with the project's own test settings

Date: 2026-10-22

## Decision

Behavioural probes now get the same test settings the project's own pytest runs get. Each side reads its own checkout, as files only:

1. The first pytest config file pytest would use: `pytest.ini`, `pyproject.toml` (`[tool.pytest.ini_options]`), `tox.ini` (`[pytest]`) or `setup.cfg` (`[tool:pytest]`).
2. From it: pytest-env `env` entries (with the `D:` default-only and `R:` raw prefixes), the pytest-django `DJANGO_SETTINGS_MODULE` key or `--ds` in `addopts`, and `pythonpath` entries inside the checkout.
3. Plain literal environment assignments at the top level of the root `conftest.py`. The file is parsed, never run.

Nothing is specific to one repository. A project's config cannot set variables that steer the runner or the sandbox, such as `PATH`, `HOME`, `PYTHONHOME` or `LD_PRELOAD`. Probe coverage runs and Contree probe runs get the same settings.

## Why

On a Django app, every probe crashed on the main side because it loaded production settings. The app refused to start without its test flags, so the probe could not count, even though the project's tests ran fine with their pytest config.
