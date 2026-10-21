# Measure coverage inside Contree

## What changed

A product check that can only run inside Contree now runs pytest with coverage in the pull-request checkpoint and reads the JSON report back. That report goes through the existing coverage gate. If the report is missing, coverage stays "not measured" and a product check that would have been verified is still capped at could not verify.

Study runs are unchanged: they still record coverage as not measured on this path. Probe coverage is still not measured in Contree-only mode. The Contree install also includes pytest-cov so the coverage run does not need a second install.

## Why

Contree-only checks used to skip coverage because bubblewrap could not start a local coverage process. Product checks then could not be marked verified, even when the tests had exercised the change.

## Decision

Run the coverage pytest remotely, on the pull-request checkpoint only, and bring the report back in the command output. Do not put any key in that command. Do not raise a verdict when the report is missing. Do not change the study path's coverage result.

## Alternatives and tradeoffs

- Keep skipping coverage: honest, but every Contree product check stays capped.
- Run coverage on the local machine: refused on purpose, because pull-request code must not run outside Contree in this mode.
- Also measure which lines each probe runs: not in this change. The AI-probe rule in full mode is unchanged.

## What it means for you

A Contree product check can be verified when coverage was measured and the other rules allow it. If the coverage file does not come back, the result stays could not verify. Contree still bills the Nebius account whose key and project id were used to start the check.
