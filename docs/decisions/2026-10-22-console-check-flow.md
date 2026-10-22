# Console check flow: setup lookup, per-run requirements and 3 retry tries

**Date:** 2026-10-22
**Status:** proposed (awaiting review)

## What changed

- A product check (console, daily) now writes two files for each run: `requirements.txt` and `setup-plan.json`. Every line comes from the project's own files or from a web lookup suggestion whose PyPI page links back to the same GitHub repository. Nothing is written by hand per repository. The list is installed together, in one install call, on both main and the PR inside that run's sandbox.
- The check reports three new steps to the console: setup lookup, set up Python and install dependencies, each with a plain-words line of what was found or installed.
- A setup or import gap found mid-run (the result is "could not verify" and the error names a missing module, library or import failure) is now looked up, fixed on both sides and rerun up to 3 tries, not once. Each try is logged in the record with the problem, what was installed and the result, and shown live as a retry step.
- The console flowchart now shows 13 clickable steps: read the PR, setup lookup, set up Python, install dependencies, install main, install PR, benchmark suite, probes, review, tests, retries, swarm report and verdict.
- A `.env.example` lists `NEBIUS_API_KEY`, `NEBIUS_PROJECT_ID` and `TAVILY_API_KEY`; `.env` is gitignored.

- A new batch order for product runs (`--batch-order`): for each pull request, the setup lookup happens first, then setup, then the run. If the lookup or the setup fails, the pull request is logged and skipped, and the batch moves on. After all the others are done, each skipped pull request is tried again: the lookup diagnoses the failure, the fix (link-back PyPI packages only) is applied on both sides and setup is retried, up to 3 tries, before the verdict is "could not verify". The order, every skip and every try are written to `batch-order.jsonl` in the run folder.
- A missing system library (for example zlib headers, or `pg_config` for libpq) is mapped to OS packages from a fixed allowlist only: `build-essential`, `pkg-config`, `zlib1g-dev`, `libpq-dev`, `libffi-dev`, `libssl-dev`, `libegl1`, `libgl1`, `libxkbcommon0`. A missing build tool (`make`, `gcc`, `cc`, `g++`) maps to `build-essential`. A missing shared library file is mapped too, for example `libEGL.so.1` to `libegl1`, `libgl1` and `libxkbcommon0` for headless GUI tests. These go through the existing system-package install path, which installs on both sides or on neither. They are installed on both sides in a sandbox that can install system packages, and the step is retried. Any other name, even one the lookup suggests, is refused and logged. A sandbox that cannot install system packages logs what is needed and the result stays "could not verify".

## Why

Projects need different Python versions and libraries. A fixed list per repository hides that work and does not carry over to the next repository. Some setup problems only show up mid-run, and one rerun was often not enough when a fix uncovered the next missing piece.

## Decision

1. The setup plan is built at run time from the project's files plus the lookup, and written as that run's `requirements.txt`.
2. Only packages the project lists, or whose PyPI page links back to the project's GitHub repository, are installed. Anything else is refused and logged.
3. Retries cover setup and import gaps only. A "needs attention" result, which is a test the PR breaks, is never retried.
4. Up to 3 tries. If the gap remains, the verdict is "could not verify" with the missing name. The advisory swarm still writes its report and cannot change the verdict.

5. In a batch, one pull request with a setup problem no longer holds up the others; it waits for the end pass.

## Alternatives and tradeoffs

- A hand-kept list per repository would be faster to start but breaks on the next repository and goes stale.
- More than 3 tries would rescue a few more checks but makes a stuck check slow for the person watching.
- The study (benchmark) mode is unchanged and does not use the plan, so published study numbers are not affected.

## What it means for you

The report now says: "If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing or fails to import, it looks up the cause, installs the fix on both sides and reruns that step, up to 3 tries."


In the console, click any step to see what was looked up, which Python was used, what was installed on both sides and every retry. Copy `.env.example` to `.env` and add your keys to run checks locally.
