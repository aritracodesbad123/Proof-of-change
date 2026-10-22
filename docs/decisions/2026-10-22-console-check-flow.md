# Console check flow: setup lookup, per-run requirements and 3 retry tries

**Date:** 2026-10-22
**Status:** proposed (awaiting review)

## What changed

- A product check (console, daily) now writes two files for each run: `requirements.txt` and `setup-plan.json`. Every line comes from the project's own files or from a web lookup suggestion whose PyPI page links back to the same GitHub repository. Nothing is written by hand per repository. The list is installed together, in one install call, on both main and the PR inside that run's sandbox.
- The check reports three new steps to the console: setup lookup, set up Python and install dependencies, each with a plain-words line of what was found or installed.
- A setup or import gap found mid-run (the result is "could not verify" and the error names a missing module, library or import failure) is now looked up, fixed on both sides and rerun up to 3 tries, not once. Each try is logged in the record with the problem, what was installed and the result, and shown live as a retry step.
- The console flowchart now shows 13 clickable steps: read the PR, setup lookup, set up Python, install dependencies, install main, install PR, benchmark suite, probes, review, tests, retries, swarm report and verdict.
- A `.env.example` lists `NEBIUS_API_KEY`, `NEBIUS_PROJECT_ID` and `TAVILY_API_KEY`; `.env` is gitignored.

- A new batch order for product runs (`--batch-order`): for each pull request, the setup lookup happens first, then setup, then the run. If the lookup or the setup fails, the pull request is logged and skipped, and the batch moves on. After all the others are done, each skipped pull request is tried again: the lookup diagnoses the failure, the fix (Python packages the project declares as a dependency or extra, read from main's copy) is applied on both sides and setup is retried, up to 3 tries, before the verdict is "could not verify". The order, every skip and every try are written to `batch-order.jsonl` in the run folder.
- A failure that needs an OS package (a missing header, shared library, tool or executable) is diagnosed for each run from that run's own sources: the project's install docs in main's checkout only (README, CONTRIBUTING, install pages, CI workflows, Dockerfile, pyproject and setup files) and lookup pages from the project's own sites, together with the failure text. The packages they name are proposed for that run. There is no hand-written package list and no error-to-package map in the code. Proposed packages go through the existing system-package install path, which installs on both sides or on neither, and the step is retried. Where the sandbox cannot install OS packages (bubblewrap), the check records a limitation in plain words with the packages it needed and the real error, and the result stays "could not verify". See docs/LIMITATIONS.md.
- Safety rules for every lookup-driven install:
  - (a) Install steps are taken only from the project's own pages: its own GitHub repository (not other repositories in the same organisation), that repository's GitHub Pages site, or a homepage or docs site the project declares in its packaging files or on its PyPI page. On a docs host shared by many projects, only the project's own path is trusted. Other sites are ignored, and the lookup's free-text answer is not used.
  - (b) A package must exist in the official source before it is installed: the distro archive for OS packages (checked with `apt-cache policy`), and PyPI for Python packages. A Python package from the batch diagnosis must be declared by the project (a runtime dependency or any extra) in main's copy; a PyPI link back alone is not enough. Packages from the first setup lookup still need a PyPI page that links back to the project.
  - (c) Only package names are taken from a page. Commands on a page are never run.
  - (d) The same setup goes on both sides, inside that run's sandbox, and each try is logged with the pages it relied on. Install docs, listed packages and system-package files are read from main's copy only, so a pull request cannot add a package that then lands on main too. When the pull request changes any of those files, the report shows a WARN line, "Install docs unchanged by the PR", and a note naming the files.
  - (e) Nothing carries over between runs: the install docs, lookup results and staged fixes belong to one run and one pull request.

## Why

Projects need different Python versions and libraries. A fixed list per repository hides that work and does not carry over to the next repository. Some setup problems only show up mid-run, and one rerun was often not enough when a fix uncovered the next missing piece.

## Decision

1. The setup plan is built at run time from the project's files plus the lookup, and written as that run's `requirements.txt`.
2. Only packages the project lists, or whose PyPI page links back to the project's GitHub repository, are installed. Anything else is refused and logged.
3. Retries cover setup and import gaps only. A "needs attention" result, which is a test the PR breaks, is never retried.
4. Up to 3 tries. If the gap remains, the verdict is "could not verify" with the missing name. The advisory swarm still writes its report and cannot change the verdict.

5. In a batch, one pull request with a setup problem no longer holds up the others; it waits for the end pass.
6. When main installs fine and only the pull request's side fails to build, that is the pull request's own failure. It is labelled "the PR's own build failure", is not retried as a setup problem (no install retries, no end-pass retries, no setup-gap retries) and the verdict stays "could not verify" with that reason. Exception: when the error text shows a missing system library, header file, pkg-config package or build tool (matched by generic error patterns, never a list of package names), it is not the pull request's fault. It stays "could not verify" with a limitation naming what is missing.
7. The batch order and the new setup-gap tries are for product runs only. A study run or the daily study that asks for `--batch-order` is refused, and those runs keep the earlier single setup-gap rerun, so their results are unchanged.
8. A file the check cannot write (this run's requirements file, setup plan or lookup cache) is reported as a warning and noted in the record, not silently skipped.

## The two retry limits

- Install retries: if installing a side fails, the install is tried again up to 2 more times. On a product run the pull request's side gets none once main has installed fine (decision 6).
- Setup-gap tries: if a test still cannot be verified because something is missing or fails to import, the cause is looked up, the fix is installed on both sides and the step is rerun, up to 3 tries. The batch end pass uses the same limit of 3 tries for a pull request whose setup failed.

## Alternatives and tradeoffs

- A hand-kept list per repository would be faster to start but breaks on the next repository and goes stale.
- More than 3 tries would rescue a few more checks but makes a stuck check slow for the person watching.
- The study (benchmark) mode and the daily study are unchanged: they refuse the batch order and keep the earlier single rerun, so published study numbers are not affected.

## What it means for you

The report now says: "If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing or fails to import, it looks up the cause, installs the fix on both sides and reruns that step, up to 3 tries."


In the console, click any step to see what was looked up, which Python was used, what was installed on both sides and every retry. Copy `.env.example` to `.env` and add your keys to run checks locally.
