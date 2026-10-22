# AI-written probes: safer writing rules and self-repair when a probe breaks itself

Date: 2026-10-22

**Status:** proposed

## Decision

Product checks only (`--product-check`). The study run and the daily study keep their probe instructions and their behaviour exactly as before; a test pins the study instructions.

1. The instructions for writing behavioural probes gain generic rules, with no project or package names: never monkeypatch or replace standard-library or runtime core functions (time and clocks, event-loop internals, random, os, sys) with finite fakes, lists or iterators; never build hand-made fake objects (mocks, stubs or stand-in classes) in place of the project's own objects; call the project's real public code with small real inputs; if a value must be controlled, use a deterministic function with no limit; keep probes simple and always print the parsed observations.
2. A probe counts as having broken itself only when every run crashed or printed no parsed output on BOTH sides, and every traceback frame is in the probe file itself or the Python standard library. A crash on one side only, or one whose traceback reaches the project's code or any installed package, is evidence and is never repaired.
3. Such a probe is rewritten by the model and rerun on both sides: the first attempt plus up to 2 rewrites, 3 attempts in total. The rewrite request contains only the probe's own source and its own error text, never either side's results or observations, so it cannot steer toward a verdict.
4. Each rewrite is frozen again before its rerun. Every crashed attempt's probe file and logs are kept, and the report gives one plain line per attempt. If the last attempt still crashes, the probe gives no evidence and the result stays could not verify.

## Why

On a pull request about slow-wait warnings, the AI-written probe replaced the clock with a short list of fake times. The list ran out inside the event loop on every run, so two claims had no observation and the check could not give a verdict. The fault was in the probe, not in the project.

## Limits

A rewrite is written after the first runs of both sides, so a rewritten probe is not frozen before the first PR-side run. Its rewrite request never sees results, which keeps it blind to the outcome, and the record marks it as a rewrite.
