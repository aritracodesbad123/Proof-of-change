# The required Python is set up automatically

Date: 2026-10-21

Status: proposed (pipeline change, needs review before merge)

## Context

A random-PR check of a repository that needs Python 3.14 ended as "rerun, setup problem": the sandbox only had Python 3.12, and a `--python` value pointing at an interpreter installed outside the sandbox could not be seen inside it. Users of the console, a Codespace or the command line should not need a flag or a manual install for this.

## Decision

- The setup plan reads the Python a project needs from its own files: `requires-python` in `pyproject.toml`, `python_requires` in `setup.cfg` or `setup.py`, `.python-version`, and the versions named in `tox.ini`, `noxfile.py` and `.github/workflows/*.yml`. Web lookup text is still never a source.
- Local sandbox: when no matching interpreter is installed, the runner downloads a uv-managed standalone CPython into uv's managed Python folder before any project code runs. That folder is already mounted read-only inside the sandbox, so both sides create their environments from the same interpreter.
- Contree: the setup shell, which runs while network is still allowed and before the checkpoints are saved, installs that Python with uv into the sandbox image and makes `python` point at it. The PR checkpoint is forked from main, so both sides use the same interpreter. Tests and probes then run offline as before.
- If an install fails with an error that names a different Python, the runner installs that Python and tries the install once more before reporting a setup problem.
- Every automatic fix is written into the report notes in plain words, starting with "Auto-fix:".
- Only the interpreter is downloaded. Project packages still come only from the project's own files. The download runs with keys and tokens removed from its environment.

## Consequences

A check of a project pinned to a newer Python than the sandbox has now runs instead of stopping at setup. The first such check spends extra time downloading the interpreter. A version uv cannot provide still ends as a setup problem, with the reason in the report.
