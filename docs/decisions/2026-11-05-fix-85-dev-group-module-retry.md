# Fix 85: install a both-sides ModuleNotFound from any dependency group

## What changed

When main and the pull request both fail with `ModuleNotFoundError` for the
same import name `X`, the setup-gap retry looks `X` up in every
`[project.optional-dependencies]` extra and every PEP 735
`[dependency-groups]` group (including `dev`), installs only the matching
requirement into the run's sandbox, and reruns once. The could-not-verify
reason names that module. Study and product retries both receive the pull
request's log directory and checkouts so pytest logs and group tables are
visible. There is no fixed module-to-package map and no per-repository case.

## Why

isort #2781 (base `841e4312`, head `3936b83f`) failed to load on both sides
because `hypothesis` and `black` live only under `[dependency-groups] dev`.
The earlier retry either skipped expanding that list (study path without a
collection-import marker) or never read the pytest logs, so it installed
nothing and reported a bare "setup gap setup". The same shape appears on any
project that keeps test-only packages in a `dev` group rather than a
`test`/`tests`/`testing` extra.

## Decision

Treat a module missing on both sides as a setup gap. Resolve it only from the
project's own declared extras and dependency groups. Name the module in the
reason. Keep the behaviour generic.

## Alternatives and tradeoffs

Installing every `dev` group package on first setup would hide the gap but
would pull in linters and docs tools the check does not need. A hard-coded
map from import name to package would break the "no per-repo cases" rule and
go stale. Leaving the study path unchanged kept isort unverified forever.

## Tests

- isort #2781 shape: fixture mirrors the base pyproject; both-sides logs name
  `hypothesis` and `black`; retry installs both from `dev` and names the
  module when still missing.
- Held-out repo: a synthetic project whose only match is a `dev`-group
  package (`fancycheck`); retry installs that one package only.
