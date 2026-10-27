# Checkout version and a verified editable install

Status: proposed

## Problem

Two live product checks on main stopped as could not verify for setup reasons, not for anything in the pull request.

1. pytest-dev/pytest#15265: the checkout was fetched with depth 1 and no tags, so setuptools_scm gave the project
   version `0.1.dev1+g<sha>`. pytest's own `minversion` setting then refused to start and no tests were collected.
2. pallets/markupsafe#512: the editable install failed. MarkupSafe builds an optional C extension; with no compiler
   in the sandbox its setup script retries without the extension in the same process, and that retry fails inside
   pip's editable build. Every editable attempt failed with its output hidden, so the deps-only fallback ran and put
   the checkout root on the path. For a `src/` layout project that is the wrong directory. The final
   `pip install --no-deps -e .` also failed, but `|| true` hid it, and the import-origin check recorded
   "not importable" with status "ok". The tests' conftest then failed with `No module named 'markupsafe'`.

## Decision (product checks only; study shells unchanged)

- Version, same text on both sides: fetch the commit with its full commit history (no file contents) and tags. When a
  tag is reachable, the version comes from it. Only when none is reachable, set a setuptools_scm pretend version from
  the repository's latest version tag, scoped to the project's own distribution name from `pyproject.toml` when it
  has one. The version source is written to an install report and recorded per side. Nothing is per repository.
- Editable reinstall: its exit code and output are kept. When it fails, the checkout's source directory (`src/` when
  present, else the root) is put on the path, and that fallback is recorded.
- Evidence: after install and before tests, with the same `python` the tests use and from `/work/src`, each side
  logs and records the interpreter, version source, editable exit code (and output tail on failure) and `pip show`.
- Fail loudly: if the editable install failed and the package still does not import from the checkout, the check
  stops as could not verify saying the pull request's own checkout did not install. A package that does not import
  after a good install is recorded as "not importable", no longer "ok".
- Each product check prints its time per stage to the log as well as the record.

## Not done

No OS packages (no compiler is installed), no per-repository rules and no hard-coded versions.
