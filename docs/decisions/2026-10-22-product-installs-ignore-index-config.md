# Product-check installs ignore uv and pip config, project uv sources and index settings

**Date:** 2026-10-22
**Status:** proposed

## What changed

- On a product check, the normal install of each side, the setup-gap retry install and the dependencies-only install run every uv call with `--no-config`. Each `uv pip install` also gets `--no-sources`, so the project's `[tool.uv.sources]` (paths, git, URLs, workspace members) cannot change where a package comes from.
- Their environment drops every `UV_*` setting about an index, find-links or insecure host and every `PIP_*` setting about an index, find-links or trusted host, and sets `UV_NO_CONFIG=1` and `PIP_CONFIG_FILE=/dev/null`.
- In Contree, the product-check setup shell starts by clearing the same settings and exporting `UV_NO_CONFIG=1` and `PIP_CONFIG_FILE=/dev/null`, so every pip and uv install in it (the project, the declared test dependencies, the optional test backends and the dependencies-only fallback) ignores config files and index settings. The dependencies-only `uv sync` lines also pass `--no-config`.

## Why

A project's `[tool.uv]`, `[tool.uv.pip]`, `uv.toml` or a pip config can add or replace the package index, add find-links or trust another host. A `[tool.uv.sources]` entry can install a dependency from a local folder or a git repository. Product checks install only from the official package index, the same way on both sides.

## Not changed

Study runs and the daily study keep their current installs. A project that only builds with its own uv sources or a private index now fails to install on a product check, and that install failure is reported as usual.
