# Product checks: keep the project's pytest addopts, strip only the flags we set ourselves

**Status:** proposed

Date: 2026-10-27. Applies to the product route only (`--product-check`). The study route is unchanged.

## What changed

On a product check, the project's own pytest `addopts` (default command-line options set in its pytest
config) are still kept, but any flag that our own test command also sets is now removed from them first.

## Why

Product checks stopped blanking the project's pytest `addopts`, so settings such as a plugin loaded with `-p` now
apply. Our own test command also sets reporting, worker, timeout and coverage flags. When a project's addopts set the
same flags (for example `--cov`, `-n auto` or `--junitxml`), pytest applies both. That can measure coverage twice,
change the worker count, or write the result file somewhere we do not read.

## Decision

1. On a product check the project's addopts are read from its pytest config in pytest's own file order:
   `pytest.toml`, `.pytest.toml`, `pytest.ini`, `.pytest.ini`, `pyproject.toml` (`[tool.pytest.ini_options]`, or a
   native `[tool.pytest]` table), `tox.ini` (`[pytest]`), `setup.cfg` (`[tool:pytest]`). The first pytest config
   found wins.
2. Only flags our own command sets are removed, by flag name, the same for every project: coverage (`--cov` and every
   `--cov-*`, `--no-cov*`), workers (`-n`, `--numprocesses`, `--maxprocesses`, `--dist`), reporting (`--junitxml`,
   `--junit-xml`, `--junit-prefix`, `-q`/`-v` and their repeats, `--quiet`, `--verbose`, `--verbosity`, `-r`, `--tb`,
   `--color`), `--timeout`/`--timeout-method`, and `-o`/`--override-ini junit_family`. Both `--flag value` and
   `--flag=value` are handled, as are joined short forms such as `-n4` and `-rfE`. `--cov` takes its next word as a
   value only when that word does not start with `-`, as pytest-cov does.
3. Everything else is kept, including `-p` plugins and other project settings.
4. When something was removed, the filtered list is passed back as `-o addopts=<filtered>`, which replaces the
   project's value, so nothing is applied twice. When nothing was removed, or there is no pytest config, no extra
   argument is passed.
5. The study route still passes `-o addopts=` exactly as before.

## Alternatives and tradeoffs

Blanking all addopts (the old behaviour) loses plugins a project needs. Keeping them unfiltered applies our flags
twice. A per-project list of exceptions would not scale and could hide real differences. Filtering by flag name costs
a short, fixed list that must grow if our command starts setting a new flag.

## What it means for you


No project is special-cased. A flag we do not set is never touched. Only the pytest config at the checkout root is read; if
there is none, pytest reads the project's settings on its own, as before.
