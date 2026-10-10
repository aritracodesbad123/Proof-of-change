# 2026-10-11: Model-written probes, the probe freeze rule, and `--baseline`

## Background, in plain words

Proof-of-Change checks a pull request (PR: a proposed change to a project's code) by building two copies of the
project, the **base side** (the code before the change) and the **PR side** (the code with the change), and
comparing how they behave.

It compares them in two ways:

- **Tests**: the project's own test suite, run on both sides.
- **Probes**: small Python scripts that call the library and print what they see. A probe runs once on each side,
  and any difference in its output is reported. A probe can also check a **claim**, which is a sentence from the
  PR description such as "this changes the order of the output columns".

Until now, every probe was written by hand, after the PR and its results were already known. That is useful for
catching regressions (old bugs coming back), but it is a weak measure of how well the tool would do on a PR it has
never seen. If you write a check after you know the answer, the check will tend to agree with the answer.

## What changed

1. **Model-written probes.** A language model (an AI system that writes text and code) can now read the PR title,
   the PR description and the base-side code, then write claims and probes. It talks to an
   OpenAI-compatible API (a common, widely copied web API format) and by default uses a Nemotron Super model.
   Its answers must follow a fixed JSON layout (JSON is a simple text format for structured data).
   - `--model-provider nebius` calls the live model. It needs the `NEBIUS_API_KEY` environment variable.
   - `--model-provider recorded` replays saved answers from `evals/fixtures/model_responses/`. These saved
     answers are **test fixtures** (fixed sample data for tests), are labelled as such everywhere, and never count
     as a real result.
   - `--model-provider none` (the default) uses only the hand-written probes. The report says so.
2. **The probe freeze rule.** Before any PR-side code runs, every probe is **frozen**: the tool records a
   fingerprint of the file (a SHA-256 hash, a short code that changes if even one character changes), who wrote it
   ("fixed" by hand or "model" plus the model id), the time, and a fingerprint of everything the writer was shown.
   On the PR side, a probe is refused if its fingerprint no longer matches or it was written after PR-side work
   started. A model is never shown PR-side code, only the description and the base side.
3. **`--baseline`**, which picks how much checking to do:
   - `tests`: tests only.
   - `tests+diff`: tests plus generic **differential probes**. These call the public functions the PR touches
     with a fixed set of simple inputs and compare the results. No model is involved.
   - `tests+probes`: tests plus claim probes, both hand-written and model-written.
   - `full` (the default): everything, including coverage (which changed lines the tests actually ran) and
     claim flagging.
   The chosen baseline is stored in each run record (schema revision 7, which only adds fields), shown in the
   report, and used by the evaluation scripts.
4. **`evals/ablation.py`** compares the baselines. An **ablation** is a study that switches parts off one at a
   time to see what each part contributes. For each baseline it reports the catch rate (real problems found), false
   alarms, and how often the tool could not reach a verdict. Results that came from non-blind probes are shown in a
   separate, clearly labelled NOT BLIND column.
5. Three smaller fixes found while testing on another library:
   - Files under a `src/` folder now count as package code.
   - Test dependencies declared in a `[dependency-groups]` table of `pyproject.toml` (a newer standard, PEP 735)
     are now installed.
   - Tests usually run in parallel worker processes (pytest-xdist). Some suites name their tests differently in
     each worker, which makes xdist stop with "Different tests were collected". That run is now repeated
     without parallel workers, instead of being counted as flaky (a test that sometimes passes and sometimes fails).

## Why

The goal is an honest number for how often the tool catches a real problem. A probe only counts as **blind**
(written without knowing the answer) when it was written by the live model, frozen before PR-side work started,
and verified unchanged afterwards. Hand-written probes and recorded fixtures stay useful as regression cases, but
they are kept out of blind scores, and a test makes sure blind scoring rejects them.

## The decision

- Generate probes only from the PR text and the base side, then freeze them, then run the PR side. The order is
  enforced in code, not just written down as a rule.
- Treat model-written code as untrusted. It runs only inside the sandbox (an isolated box with no network
  access), with a time limit and a limit on how much output it may produce. Its output must match a fixed format,
  or the result is thrown away.
- The API key stays in the process that coordinates the run and is never passed into the sandbox. A test checks
  this.
- Keep the old behaviour as the default for anything that touches money or keys: no model is called unless you
  ask for one.

## Alternatives considered, and the tradeoffs

- **Let the model see the PR-side code.** It would write sharper probes, but they would no longer be blind, which
  defeats the point. Rejected.
- **Trust a written promise instead of fingerprints.** Simpler, but nothing would stop a probe being edited after
  the results came in. Fingerprints and timestamps cost little.
- **Mix blind and non-blind results into one score.** One number is easier to read, but it would quietly inflate
  the result. They are reported side by side instead.
- **Use only the model, with no generic differential probes.** Differential probes are cheap and need no key, so
  they give a model-free middle step between "tests only" and "tests plus claims".
- Costs: `full` runs take longer (on one sample PR with recorded model probes, about 155 s instead of about 75 s)
  because more probes run.
  When a key is used, live model calls also cost money.

## What this means for you as a user

- The default is `--baseline full --model-provider none`, so no model is called unless you ask for one. One
  thing does change by default: `full` now also runs the generic differential probes. Their results are shown
  for information only and do not decide the verdict, but they make runs somewhat slower.
- To try model-written probes, set `NEBIUS_API_KEY` and add `--model-provider nebius`. Without a key, the run falls
  back to the hand-written probes and the report says so.
- Reports now show the baseline used, who wrote each probe, its frozen fingerprint, and any probe that was refused.
- If you add hand-written probes, they are labelled as written after the fact and do not count towards blind
  scores. That is expected.
- Run `python evals/ablation.py --help` to compare baselines on a set of PRs.
