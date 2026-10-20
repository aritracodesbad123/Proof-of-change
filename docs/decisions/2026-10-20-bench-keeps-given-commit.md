# Benchmark mode runs the commit it is given

## What changed

A benchmark run used to fetch `origin` and move the checkout to `origin/main` before it tested anything. It now stays on the commit that is already checked out.

You name that commit with `--expect-commit` or with `POC_EXPECT_COMMIT`. The run stops if HEAD is not that commit, or if the work tree has uncommitted changes. It does not fetch, check out, or merge. The message says the checkout was not moved.

Every result record still stores the commit the run used, in `poc_commit`. For a benchmark run that is the expected commit. A daily run and a one-off check still fast-forward to `origin/main`, and they still store that commit on each record.

## Why

A benchmark is a measurement of one known build of this tool. Moving the checkout to `origin/main` first meant the run could test a different build from the one that was handed to it. The records then named that other commit, so a later reader could not see which code had actually produced the numbers.

## Decision

- In benchmark mode, do not fetch and do not change the checkout.
- Require the expected commit (`--expect-commit` or `POC_EXPECT_COMMIT`). Refuse to start when it is missing, when it is not a 40-character commit, when HEAD is different, or when the work tree is dirty.
- Store that commit on every record as `poc_commit`.
- Leave daily runs and one-off checks as they are: they still fast-forward to `origin/main` and record the commit they landed on.

## Alternatives and tradeoffs

Keeping the fast-forward would make every benchmark run the same commit as production, which is useful for a scheduled daily check and wrong for a measurement of a specific build. The two modes now do different things on purpose.

Refusing a dirty tree means a benchmark cannot start while edits are sitting in the checkout. That is the same caution the daily run already uses, without the follow-on step of moving to `main`.

## What it means for you

Start a benchmark from a clean checkout of the commit you mean to measure, and pass that commit as `--expect-commit`. If the checkout is dirty or HEAD is something else, the run stops and leaves the checkout where it was. A daily run still updates itself to `origin/main` and writes that commit on its records.
