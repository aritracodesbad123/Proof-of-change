# Product-check installs ignore uv and pip config, project uv sources and index settings

**Date:** 2026-10-22
**Status:** proposed

## What changed

- On a product check, the normal install of each side, the setup-gap retry install and the dependencies-only install run every uv call with `--no-config`. Each `uv pip install` also gets `--no-sources`, so the project's `[tool.uv.sources]` (paths, git, URLs, workspace members) cannot change where a package comes from.
- Their environment drops every `UV_*` setting about an index, find-links or insecure host and every `PIP_*` setting about an index, find-links or trusted host, and sets `UV_NO_CONFIG=1` and `PIP_CONFIG_FILE=/dev/null`.
- In Contree, the product-check setup shell starts with a plain `unset` of a fixed list of index and config settings (for example `UV_INDEX`, `UV_INDEX_URL`, `UV_EXTRA_INDEX_URL`, `UV_DEFAULT_INDEX`, `UV_FIND_LINKS`, `UV_NO_INDEX`, `UV_INSECURE_HOST`, `UV_INDEX_STRATEGY`, `UV_CONFIG_FILE`, `PIP_INDEX_URL`, `PIP_EXTRA_INDEX_URL`, `PIP_FIND_LINKS`, `PIP_NO_INDEX`, `PIP_TRUSTED_HOST`, `PIP_CONFIG_FILE`), then exports `UV_NO_CONFIG=1` and `PIP_CONFIG_FILE=/dev/null`. A check line follows: if any listed setting is still set, or the two exports did not take, the shell stops with an error before anything is installed. Every step ends with `|| exit 1`, so a failed unset or export also stops it. Every pip and uv install in that shell (the project, the declared test dependencies, the optional test backends and the dependencies-only fallback) runs after this, and the dependencies-only `uv sync` lines also pass `--no-config`.
- A product check whose project needs its own package index or uv sources (`[tool.uv.sources]`, `[[tool.uv.index]]`, a uv workspace, or index, find-links or trusted-host keys in `[tool.uv]`, `[tool.uv.pip]` or `uv.toml`) and fails to install ends as could not verify, with an `unsupported:` reason that names those settings. This holds on either side, locally and in Contree, and it is never needs attention.

## Why

A project's `[tool.uv]`, `[tool.uv.pip]`, `uv.toml` or a pip config can add or replace the package index, add find-links or trust another host. A `[tool.uv.sources]` entry can install a dependency from a local folder or a git repository. Product checks install only from the official package index, the same way on both sides.

## Not changed

Study runs and the daily study keep their current installs. A project that only builds with its own uv sources or a private index cannot be installed on a product check and ends as could not verify, as above.
