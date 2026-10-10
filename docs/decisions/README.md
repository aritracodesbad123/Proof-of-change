# Decision log

This folder records why the project changed, one decision at a time. Read it to understand how the tool got to
where it is, or before you change something that was decided on purpose.

## One file per pull request

Every pull request (a proposed change to the code, reviewed before it is merged) that changes code adds one new
file here:

```
docs/decisions/YYYY-MM-DD-<short-topic>.md      for example 2026-10-11-benchmark-scorer.md
```

The date is when the change was made. The topic uses lower-case letters, digits and hyphens. Each pull request
gets its own new file, so two pull requests worked on at the same time never edit the same file and never
conflict.

"Code" means anything under `poc/`, `harness/`, `evals/`, `guardrails/`, `reports/`, `ops/` or `.github/`. A
change to the docs alone does not need an entry, though one is welcome.

## What goes in an entry

Use these headings:

1. **What changed**: the change in a few sentences.
2. **Why**: the problem it solves.
3. **Decision**: what we chose to do.
4. **Alternatives and tradeoffs**: what else we could have done, and what this choice costs.
5. **What it means for you**: what someone using the tool will notice, and anything they need to do.

Write for a beginner-to-intermediate reader. Use plain words and short paragraphs, and explain every technical term
the first time it appears. The repository is public, so leave out people's names, machine-specific paths and
internal schedules.

## The check

CI (the automatic checks that run on every pull request) runs `python -m guardrails.decision_log --base
origin/<base branch>`. It fails when a pull request changes code without adding a new file that matches the name
pattern above. Editing an older entry does not count, because each change needs its own record.
