# The daily picker skips projects whose requirements need compiling

**Date:** 2026-10-22
**Status:** accepted

## What changed

- Before the daily picker selects a pull request, it reads the project's runtime requirements from the default branch: `[project].dependencies` in `pyproject.toml` and the plain lines of a top-level `requirements.txt`. Options (`-r`, `-e`, index and find-links lines), URLs, direct references and local paths are dropped, so nothing read from the project can change where packages come from.
- It then does a dry-run resolve with `uv pip compile --only-binary :all:` for the Python version the checks use (`--python`, default 3.12) on Linux x86_64. Nothing is built or installed. The uv call and its environment go through `isolated_install`, as product installs do: `--no-config`, no index or find-links settings, no pip config file. Environment variables that look like keys or tokens are not passed to it.
- If any package has no ready-built wheel, every pull request of that project is skipped in that run with `skipped: needs compiling (<package>)`. If the requirements do not resolve at all, the reason is `skipped: requirements do not resolve to ready-built wheels (<first error line>)`. The check runs once per project per run.
- `--no-wheel-check` turns the check off.

## Why

Some projects written in Python depend on packages that must be compiled from C or C++ or need a system library. Checks cannot compile or install system packages, so those pull requests always end as could not verify for a setup reason. Skipping them at pick time keeps the daily results about the pull requests themselves.

## Not changed

Single pull-request checks (`--pr`), chosen PRs and frozen selections do not run this check, and the study pair-gathering scripts are not changed. No operating-system package is installed. Test-only and optional requirements are not part of the dry run, so a project can still fail setup later on one of those.

The daily picker's output never feeds into study runs: `select_prs` is called only from the daily selection loop in `ops/daily_run.py`, study (bench) runs return through `bench.run` before that loop is reached, and the study pair-gathering script `evals/gather_study_pairs.py` reads only its own `--candidates` file, not the picker's selection.
