# Benchmark cases, runner and summary

The benchmark measures whether a check catches regressions that the project's own tests miss. It runs every
case twice on the same commits and the same Contree sandbox: once with the test comparison only, and once with
model-written probes added. It then counts what each arm caught.

## Case file

Each case is one JSON file in `bench/cases/`. All fields except `fixture`, `patch` and `notes` are required.

| Field | Meaning |
|---|---|
| `schema` | always `poc-bench-case/1` |
| `id` | unique, 1-64 letters, digits, `.`, `_` or `-` |
| `repo` | `owner/name`, one of the benchmark repositories (`bench/manifest.py`, `ALLOWED_REPOS`) |
| `pr_url` | the pull request the product check runs on, `https://github.com/OWNER/REPO/pull/N`, in `repo` or in `fork` |
| `fork` | optional: `OWNER/REPO` of a fork that holds the PR, with the same repository name as `repo`. `repo` still names the upstream project from the list |
| `base_sha`, `head_sha` | full 40-character commits: the base the check must compare against, and the PR head. They must differ. For a fork PR, `base_sha` is still the upstream commit, so the fork's base branch must sit on it |
| `category` | `known_safe`, `known_regression_tests_catch`, `known_regression_tests_miss`, `setup_failure` or `ambiguous` |
| `expected_verdict` | `verified` for known_safe, `needs_attention` for both regression kinds, `could_not_verify` for setup_failure, any verdict for ambiguous |
| `rationale` | why the expected verdict is the ground truth |
| `source` | where the case comes from (merged fix, issue, planted patch) |
| `patch` | optional: the stored `.patch` or `.diff` that the PR head carries, for a planted regression |
| `fixture` | `true` only for unit-test fixtures. The runner refuses fixture cases |

A planted regression is run through a pull request, usually on a fork, whose head carries the patch, so it uses the same product
check path as any other case. Check the case files with:

```bash
python -m bench.manifest bench/cases
```

## Runner

```bash
python -m bench.run --cases bench/cases
```

Add `--swarm-arm` for a third arm with the advisory swarm on, and `--case ID` to run only some cases. Each
run is `ops/daily_run.py --pr URL --product-check --sandbox-backend contree` with `POC_REQUIRE_CONTREE=1`, so a
missing Contree setup stops the run instead of falling back to local. The tests-only arm uses
`--baseline tests --model-provider none` and makes no model calls. The probes arm uses
`--baseline tests+probes --model-provider nebius`.

One JSON result per case and arm goes to `bench/results/<date>/<arm>/<id>.json`. It holds the verdict, the
install, tests, probes and infrastructure stage states, the wall time, the model calls, tokens and cost from the
check's record, the commits actually tested, the command and the exit code. Secret values are removed from
saved error output. `run_meta.json` holds the environment, with keys shown only as set or unset.

A case counts as not run when the check left no record, when its tested base is not `base_sha`, when its
tested PR head or PR side is not `head_sha`, or when the record does not show a Contree run (backend `contree`
and both checkpoints built there). An open PR whose base branch has moved is therefore not run, never scored.
So is a mergeable open PR that the check tests as GitHub's test merge commit, because that commit is not the
head. Cases should use PRs the check compares as merge-base against PR head, such as a fork PR opened from a
branch whose parent is `base_sha`.

## Summary

```bash
python -m bench.summarize bench/results/X
```

It writes `summary.json` and `summary.md`. For each arm it reports, always with n: wrong approvals (verified on a
regression), bugs caught (overall and on tests-miss cases), false alarms (needs_attention on a safe case),
verification coverage, the could-not-verify or not-run rate, setup failures, runtime, model calls and cost.
The case list and n come from `run_meta.json`; a case with no result file counts as not run. A case that did
not run or ended could_not_verify is a miss, never a catch. Probe uplift is the number of regression cases that
tests+probes caught and tests-only did not; the reverse count is shown too. A case is compared only when both
arms ran on the same commits, both installs succeeded, tests-only reached a decided verdict, and the
tests+probes flag comes from a probe finding with the same values on all 3 runs of each side. Every other
regression case is listed as excluded, with the reason. No statistical significance is claimed.
