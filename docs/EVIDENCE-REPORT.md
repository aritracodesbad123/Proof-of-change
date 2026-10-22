# Evidence report

A judge-readable report for one benchmark results folder. It is generated from the raw files
`bench/run.py` writes and from the counts `bench/summarize.py` already computes. It does not run a
check, call a model, or change a verdict.

## Command

From the repository root:

```bash
python -m bench.report bench/results/2026-10-22
```

That writes `evidence.md` and `evidence.html` in the results folder. Both are built from the same
data. The HTML file is self-contained: its stylesheet is inline, and it loads no other files.

```bash
python -m bench.report bench/results/2026-10-22 --out /tmp/evidence
```

`--out` writes the two files in another directory. The results folder is only read.

## What it reads

- `run_meta.json` — the case list, the arms, and the run metadata. `n` comes from this case list.
- `<arm>/<case id>.json` — one result per case and arm (`tests`, `tests_probes`, and
  `tests_probes_swarm` when that arm was run).
- `ops/<arm>/runs/bench-<case id>/*/record.json` — the check record, when exactly one is there.
  The report uses the same lookup as the runner. Zero records or more than one means the record
  was not recorded.

A case with no result file counts as not run, the same way the summary counts it. The report does
not read case files, logs, or anything outside this folder.

## Top of the report

The summary text is the text `bench.summarize` produces for this folder (`summary.md`), including
its fixture banner when the results are fixtures. Under that, each metric is shown with the count
and `n` stored on the summary object. The probe-uplift table lists cases caught by tests+probes but
not by tests-only, the reverse count, how many regression cases were compared, and every excluded
case with the reason the summary recorded. No rate is recomputed here.

## Each case

The first line is the decision. It repeats the recorded verdict of the tests-only arm (`tests`) and
the tests+probes arm:

```text
Decision: tests=verified; tests+probes=needs_attention.
```

The token is the stored verdict: `verified`, `needs_attention`, `could_not_verify`, or
`no_code_change`. An arm that did not run is `not_run`. A missing or unrecognised verdict is
`not recorded`. The line is built only from those recorded verdicts. Model text and swarm notes
are not part of it, and it does not raise or lower a verdict. When either deciding arm is present,
the swarm arm is left off this line.

Under the decision, each arm shows:

| Item | Source |
|---|---|
| Repo | check record `repo`, otherwise the owner/name in the recorded pull-request URL |
| Pull request | check record `pr.url`, otherwise the `--pr` value stored on the arm result |
| Tested base SHA | `tested.base_sha` |
| Tested PR SHA | `tested.pr_sha` |
| PR side | `tested.pr_side` (`head` or `merge_ref`) |
| Install, tests, probes, infra | `stages` |
| Verdict | the same token as the decision line |
| Runtime | `wall_seconds` and `check_duration_s` |
| Model calls and cost | `model.ai_calls`, token counts, `provider`, `model.cost_usd` |

Record text and model text are written inside a fenced code block. The fence is longer than any
backtick run in that text, so a line inside it cannot become a heading or a `Decision:` line.
Table cells are kept on one line.

The strongest supporting evidence is quoted next, per arm, and only from executed results: a probe
finding that held on all 3 runs of each side (the same condition `bench.run.probe_held` uses), then
failing test names from `comparison.regressions`, `comparison.new_tests_failing`, and
`comparison.pr_unstable`. When neither was recorded, the quote is the check's recorded reason.

## Sections

These stay separate. A sentence in one section is not treated as evidence for another.

1. **Verified behaviour** — executed evidence: the recorded reason, failing test names, a probe
   result that held on all runs, and how many tests the record says ran.
2. **Inferred explanation** — model text from the record's `explanation` field. It is not executed
   evidence.
3. **Advisory notes** — swarm notes from the record's `agents` field, and the advisory arm's
   recorded verdict when `tests+probes+swarm` was run. Advisory notes do not change the decision line.
4. **Unverified / not run** — `not_run_why` for an arm that did not run, the could-not-verify reason
   when the verdict is `could_not_verify`, and unresolved uncertainties stored on the record (flaky
   tests, probe labels `flaky`, `needs_human`, `unstable_on_pr`, and `not_testable`, and
   `demo_helper.limitations`).

## Missing fields and secrets

A field that is absent, null, or blank is the words `not recorded`. An empty list that was stored
is `none`. Nothing is filled in from another case or from a guess.

Before the files are written, the whole report passes through `bench.run.redact_all`, the same
helper the runner uses on a result. Secret values present in the environment are removed.

## Fixtures

When any result or case is marked `fixture`, the report starts with `SAMPLE` and keeps the summary's
fixture banner. Those runs are unit-test data, not benchmark results.

## What this does not do

The report does not change verdict rules, `bench/run.py`, the summary maths, the daily run, the
study, or `replay/`. It only reads a finished results folder and writes the two report files.
