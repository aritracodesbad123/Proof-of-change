# Benchmark case files carry no verdict hints

## What changed

The known-answer benchmark's case files (claim, recorded evidence, code before and after) may no longer contain
any verdict label, in any spelling (spaced, hyphenated or underscored, any case), or any value from the answer key.
The one exception is the recovery-rerun cases. That step reads a first-run verdict and a rerun verdict as inputs.
Only those two exact fields may hold a label, and the rerun's must differ from the case's answer.
A test also watches every file the runner opens while it runs all cases, and fails if the answer key is among them.
The benchmark's notes now say plainly that it checks the verdict rules against fixed recorded evidence. It does not
test package installs or the quality of AI-written probes; runs on random real pull requests cover those.

## Why

A case that names a verdict hints at its own answer. Keeping labels out of the inputs keeps the score honest.
