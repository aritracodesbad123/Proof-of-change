# Benchmark scorer, answer-key firewall and probe lint

## What changed

Three new building blocks, plus a check that keeps this decision log going:

- a **scorer** (`evals/score_bench.py`) that says how well the tool did on a benchmark;
- an **answer-key firewall** (`poc/leakage.py`) that stops the answers from reaching anything that writes tests;
- a **probe lint** (`poc/probe_quality.py`) that rejects badly written probes before they run;
- the **decision-log check** (`guardrails/decision_log.py`) and this folder's README.

A *benchmark* is a fixed set of past pull requests where we already know the outcome: some later turned out to
break things (*regressions*), and some did not (*safe controls*). The *answer key* is the file that says which is
which. A *probe* is a small script that runs on the code before and after a change and prints what it observes,
so plain code can compare the two.

## Why

To make honest claims about the tool, we need to measure it on cases with known answers. That raises two risks.
First, the numbers can be presented badly: with only 15 or 19 cases, a single percentage hides how uncertain it
is. Second, the answers can leak: if a model that writes probes sees the answer key, even partly, it can "find" a
bug it was told about, and the results mean nothing.

Probes also need basic quality rules. A probe that asserts an expected value is judging, not observing. A probe that
opens a network connection is not repeatable. A probe that never imports the changed code cannot test the change.

## Decision

- **Scorer.** Results are joined to the answer key by case ID only, never by repository or pull request number,
  so a mismatch cannot quietly pair the wrong rows. Every rate comes with a *Wilson interval*, a range that likely
  contains the true rate and stays sensible at small sample sizes. Two settings run on the same cases are compared
  with an *exact McNemar test*. That test looks only at the cases where the two settings disagree and asks how
  likely that split would be by chance. Only the Python standard library is used. The ID and label columns can be
  configured, so any answer key works.
- **Firewall.** `check_bundle()` looks at everything a generator is about to see (the *prompt bundle*). It refuses
  the bundle if it contains any web address, issue or pull request number, or phrase from the answer key, or any
  file that exists only in the new version of the code. The answer key is first turned into *fingerprints*
  (SHA-256 hashes: one-way codes that can be matched but not read back). Refusal messages never print the matched
  text.
- **Lint.** The probe is parsed into a syntax tree and never run, so tricks such as renaming an import do not slip
  past a text search. It rejects `assert`, `pytest.raises`, network modules, process-starting calls, writes outside
  the temporary folder, and probes that import none of the changed modules.

## Alternatives and tradeoffs

- *Plain percentages instead of intervals:* simpler to read, but they overstate certainty. With 15 cases, 5 found
  means somewhere between about 15% and 58%.
- *Letting the firewall compare plain text:* easier to debug, but then every machine that checks bundles holds the
  answers. Hashing costs a little clarity in error messages, and we accept that.
- *Phrase matching* can refuse a bundle that is innocent but happens to share a five-word run with the answer key.
  We prefer a false refusal to a leak. Library files that are byte-identical to the old version are exempt from the
  phrase rule, because they existed before anyone wrote the answers.
- *Lint by regular expressions* would be shorter, but it is easy to fool and gives false hits inside strings.

## What it means for you

- Score a benchmark run with `python -m evals.score_bench --answers <answer key> --results <folder>`.
- If a generator's bundle is refused, the message names the rule and the part of the bundle that failed. Remove that
  material. Do not work around the check.
- A probe that fails the lint has to be rewritten to observe and print, not judge.
- From now on, a pull request that changes code needs a new file in `docs/decisions/`, or CI fails.
