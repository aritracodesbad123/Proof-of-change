# Contree mode never installs or runs pull-request code locally

Date: 2026-10-22

## Decision

1. When a check uses `--sandbox-backend contree`, nothing from the pull request is installed or run locally, not even as a first step. Both the main and the PR side are built directly in Contree from the setup plan, including the Python version the project needs and its dependencies. This applies whether or not bubblewrap can start.
2. If Contree cannot build the two sides, the check is refused. There is no bubblewrap fallback in Contree mode. This keeps the refusal rule from the console decision.
3. The record says `machine: contree` only once both Contree checkpoints were actually built. Until then, or if Contree never ran, it says `contree (not run)`.
4. When an install says it needs a different Python, the retry only uses an interpreter the local sandbox can see, or one we installed for this check. An interpreter in a home folder or a virtual environment link is skipped.

## Why

A live check of an app-style repo ran its installs locally before Contree was ever called. It failed there, yet the record still said the machine was Contree. The retry also picked an interpreter the sandbox could not see.
