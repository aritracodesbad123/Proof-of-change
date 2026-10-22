# Benchmark: 10 known-safe and 2 ambiguous cases go in first

**Status:** proposed

## What changed

`bench/cases/` gets 12 case files, one upstream pull request each from attrs, boltons, click, isort,
jsonschema, markupsafe, prettytable, requests, rich, sqlparse, toolz and urllib3: 10 known-safe and 2
ambiguous. All 12 pass the case file checker (`python -m bench.manifest bench/cases`). No code changed.

Why 2 are ambiguous: attrs #1647 changes astuple output on purpose, and click #3878 changes CliRunner output on
purpose. For those, needs_attention is a fair answer, so they are reported but not scored, and a flag on them
is not counted as a false alarm.

"Known-safe" here means no known regression, not proof of safety. Each rationale gives the head suite result
it rests on. Failures listed as pre-existing come from the test environment, not the PR. For click that is 24
test_echo_via_pager failures (8 tests x 3 pager variants), because the `less` pager is not installed there.

isort #2737 was open when its commits were taken and was merged later the same evening. Its case says so.

## What is not included

Only these 10 known-safe and 2 ambiguous cases are included. The planted-regression cases, their patches and any bundles are left
out. They wait for the fork trial, which has to show that a PR on a fork resolves its sides correctly through
the check before any fork case is trusted.

## Before the live run

An open PR's base branch keeps moving, and the runner counts a case as not run when the tested base is not the
case's `base_sha`. Each case records its base as the merge base as of 2026-10-22 22:40 IST
(`base_is_merge_base_as_of_2026-10-22_22:40_IST`). `base_sha` is refreshed right before the live run, and the
head is checked again at the same time. The pilot has not been run.
