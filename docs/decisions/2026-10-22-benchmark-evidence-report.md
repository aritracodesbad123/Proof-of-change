# Benchmark evidence report

**Date:** 2026-10-22
**Status:** proposed

## What changed

`bench/report.py` writes `evidence.md` and a self-contained `evidence.html` from one finished benchmark
results folder. `docs/EVIDENCE-REPORT.md` describes the command. The report reads the files the runner
already writes and the counts `bench.summarize` already computes. It does not run a check and it does
not change a verdict.

## Why

A judge needs one place that shows, for each case, what was tested, what the check recorded, and what
was only model text. Those have to stay apart, and text from a record must not be able to look like the
report's own decision line.

## Decision

- The report reads `run_meta.json`, each arm's `<arm>/<case id>.json`, and the check record at
  `ops/<arm>/runs/bench-<case id>/*/record.json` when exactly one record is there. A missing
  `run_meta.json` stops with the same plain error `bench.summarize` raises. A case with no result file
  counts as not run.
- The decision line copies the recorded verdict of the tests-only arm and the tests+probes arm
  (`verified`, `needs_attention`, `could_not_verify`, `no_code_change`, or `not_run`). It never raises,
  lowers, or replaces that verdict. Model text and swarm notes are not part of the line.
- Record text and model text are placed in a fenced code block whose fence is longer than any backtick
  run in the text. A line inside that block cannot become a heading or a decision line. Table cells stay
  on one line.
- The whole report passes through `bench.run.redact_all` before it is written.
- When a result or case is marked fixture, the report is marked `SAMPLE`.
- A field that is absent, null, or blank is the words `not recorded`. An empty list that was stored is
  `none`.

## Alternatives and tradeoffs

- Copying the record into the page as ordinary paragraphs would be easier to read, and a record could
  then forge a `Decision:` line or a `SAMPLE` heading. Fenced blocks keep the quote and the structure apart.
- Recomputing the verdict from the evidence would hide disagreements. Copying the stored verdict keeps
  the report from becoming a second judge.

## What it means for you

From the repository root, `python -m bench.report bench/results/<date>` writes `evidence.md` and
`evidence.html` in that folder. `--out DIR` writes them somewhere else. The results folder is only read.
