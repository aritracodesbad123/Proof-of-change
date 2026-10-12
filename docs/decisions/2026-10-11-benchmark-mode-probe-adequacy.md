# Benchmark mode and probe adequacy

## What changed

Two additions:

- **Benchmark mode** (`ops/daily_run.py --bench <inputs file> --ids B01,B14`) runs the normal checker on old,
  already-merged pull requests listed in a benchmark *inputs file*.
- **Probe adequacy** (`poc/probe_adequacy.py`) checks whether each probe actually runs the code that changed. A
  probe that does not is marked `not_adequate` and can no longer help a pull request get the `verified` verdict.

A *pull request* (PR) is a proposed change. When it is merged, Git creates a *merge commit* (a snapshot of the code
with the change in). That commit's *first parent* is the snapshot just before it. A *probe* is a small script that
runs on both versions and prints what it sees, so plain code can compare them. *Coverage* is a record of which lines
of code ran.

## Why

To measure the tool honestly we need to run it on past changes whose outcome we already know, and in exactly the
form they landed. Doing that by hand is slow and easy to get wrong.

A probe can also look reassuring without proving anything. If it never reaches the changed lines, it prints the same
output on both versions whatever the change did. Counting that as evidence would make "verified" mean less than it
says.

## Decision

- **Benchmark mode** builds the "before" side from the merge commit's first parent and the "after" side from the
  merge commit, both fetched by their exact commit IDs. If the first parent in the inputs file is wrong, the case
  is refused rather than run on the wrong code. Each case then goes through the same steps as a live check. The
  mode writes one result file per case and setting (`runs/bench-v0/<ID>-<setting>.json`). It refuses to open any
  file whose name contains `answers`, so the answer key (the file that says how each case really turned out) cannot
  be read by accident. Only the separate scorer reads it.
- **Probe adequacy**: after the normal probe runs, each probe runs once more on the "before" side under coverage.
  Its result records how many changed lines it ran. If it ran none, it is `not_adequate`. Its "no difference" and
  "claim proven" results are then ignored, and it does not count as checking a promise in the PR text. Any
  difference it does find is still reported, because hiding a real difference is worse than a weak probe.

## Alternatives and tradeoffs

- *Testing the PR's last commit instead of the merge commit*: simpler, but that is not what users received. The
  merge commit is what landed.
- *Measuring probe coverage on the "after" side*: on the "before" side we can see whether the probe reaches the
  lines that were about to change. The cost is that lines which exist only in the new version are invisible there.
  Where a change only adds lines, we count the lines on either side of the insertion point instead. A file that is
  brand new has no "before" lines at all, so a probe for it is marked `not_adequate`. That is strict, and we chose
  strict on purpose.
- *Blocking when coverage cannot be measured at all*: safer, but it would stop daily checks on machines where
  coverage fails to install. Instead these probes are marked `unmeasured` and the report says so.
- The extra coverage run adds a few seconds per probe.

## What it means for you

- Run a benchmark case with `python3 ops/daily_run.py --bench bench/benchmark-v0.csv --ids B01`.
- Reports may now show `not_adequate` next to a probe. Such a probe needs to call the changed code before it can
  support a `verified` verdict.
- Verdicts that used to rest on a probe that never reached the change may now read `could_not_verify`. That is
  intended.
