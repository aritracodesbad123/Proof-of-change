# Benchmark: the 12 known-safe cases go in first

**Status:** proposed

## What changed

`bench/cases/` gets 12 case files, one known-safe open pull request each from attrs, boltons, click, isort,
jsonschema, markupsafe, prettytable, requests, rich, sqlparse, toolz and urllib3. All 12 pass the case file
checker (`python -m bench.manifest bench/cases`). No code changed.

## What is not included

Only the known-safe cases are included. The planted-regression cases, their patches and any bundles are left
out. They wait for the fork trial, which has to show that a PR on a fork resolves its sides correctly through
the check before any fork case is trusted.

## Before the live run

An open PR's base branch keeps moving, and the runner counts a case as not run when the tested base is not the
case's `base_sha`. So `base_sha` in each case is refreshed right before the live run, and the head is checked
again at the same time. The pilot has not been run.
