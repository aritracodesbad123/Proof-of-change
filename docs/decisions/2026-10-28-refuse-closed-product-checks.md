# Every product check of a pull request's current code refuses a closed or merged one

Status: proposed

## What changed

Before, only runs started with `--live-check` (the console, the GitHub App and the request worker) re-read the
pull request's state and refused one that was not open. A product check started by hand with `--product-check`
skipped that step. On 2026-10-27 one such run tested pytest #15265 about three hours after it was closed.

Now every product check that tests the pull request's current code re-reads its state from GitHub first. It
refuses before any lookup, install or run when the pull request is closed or merged, when its state is missing,
or when the read fails. The reason is one plain line, for example "refused: this pull request is closed or
merged, not open, so it was not tested; a product check only tests open pull requests". The verdict is could
not verify and the record keeps `pr_state_refusal`.

Benchmark cases are the one exception. They pin both commits with `--base-sha` and `--head-sha`, so a closed
known-answer pull request still runs, and GitHub is not asked. Every shipped case in `bench/cases` is pinned,
and a test checks that.

## Python version, recorded as it is

Checks run in Contree on the base image `python:3.12-slim-bookworm`. On 2026-10-27 that was Python 3.12.15
on both sides. The setup plan uses one Python on both sides, the lowest that meets both main's and the pull
request's requirements, and starts from the image's 3.12 when that already meets them. Each record already
stores the exact version in `python` and `contree.python.main` / `contree.python.pr`.

Some research notes said these runs use Python 3.14. That is not what the checks run: 3.14 was the
interpreter on a separate pre-check machine. Nothing in the checker changes for this. Results should be
read against the version in the record. A change that only shows on another Python version stays could not
verify, or is missed.

## Why pytest #15265 loaded a released pytest

On that run the project was installed first, then the plan's requirement files. Those include pytest
plugins, and installing them pulled a released pytest from PyPI over the checkout. The tests then imported
`_pytest` from site-packages. A shallow clone without tags also gave the checkout version `0.1.dev1`, which
fails pytest's own `minversion`. The open "checkout version and editable install" pull request fixes both
generically, with no per-repo setting: it fetches tags for the real version, reinstalls the checkout last
without dependencies, records the result, and falls back to a src-layout path. It is not part of this change.
