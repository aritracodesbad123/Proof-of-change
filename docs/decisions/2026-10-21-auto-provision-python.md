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
- Where the interpreter comes from: only uv's own managed CPython builds (python-build-standalone), which uv checks against the SHA-256 in its built-in download list. Mirror and download-list settings are cleared before the download, and the uv used inside Contree is pinned. Nothing a pull request supplies (a URL, a script, a lock file entry) can choose the source.
- Which version wins: one version is used on both sides, the lowest that meets the requirements of both main and the pull request. If no version meets both, the check stops as a setup problem, and the report records each side's requirement and the version each would use. There is no fallback to one side's version.
- Hard gate: if the Python setup fails, the check stops with "setup problem: Python X could not be installed" and nothing is tested. If the dependency install fails after its automatic retries, it also ends as a setup problem. A setup failure is never verified.
- Product checks only: all of this applies only to checks started with `--product-check`. A study run keeps the earlier behaviour, so results from the v1.1 tag do not change.
- The console's process graph shows two new steps before the tests, "Set up Python <version>" and "Install dependencies", each with its state and, when clicked, what was installed or fixed.
- Projects that cannot be built as a package: when the project install fails because the project itself cannot be built (for example a flat-layout error, or an application meant for `uv sync`), only the dependencies it declares are installed. With `uv.lock`, the lock is exported without the project (`--frozen`), which gives the same set as `uv sync --no-install-project`. With only `pyproject.toml`, its dependencies are exported the same way. Otherwise its `requirements*.txt` files are used. Both sides use the same commands, and the project folder goes on the import path. This is logged as an "Auto-fix:" line. If it also fails, the check ends as a setup problem. The wrong-commit guard then checks that the import-path entry names exactly that side's checkout and that the checkout is at the requested commit; anything else still fails closed.
- Only the interpreter is downloaded. Project packages still come only from the project's own files. The download runs with keys and tokens removed from its environment.

## Consequences

A check of a project pinned to a newer Python than the sandbox has now runs instead of stopping at setup. The first such check spends extra time downloading the interpreter. A version uv cannot provide still ends as a setup problem, with the reason in the report.
