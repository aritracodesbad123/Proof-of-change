# Requirement files, the import package, and which files are tests

## What changed

A pip requirements file counts when its name contains `requirements` and ends in `.txt`. `dev-requirements.txt` and `test-requirements.txt` are included, not only names that start with `requirements`. A line `-r` or `--requirement` in those files, and the same line in a tox `deps` setting, is followed, including when the included file includes another. A cycle stops. A path with `..`, a URL, or a path that leaves the project is not followed. Those lines are declared test dependencies: they are installed with the other requirement files, and the setup-gap retry can see them. The same filename rule is what the dependencies-only install reads.

For a repository that is not one of the built-in libraries, the import package is read from the checkout. `packages` and `package-dir` in `setup.cfg` or `pyproject.toml` win when they name a single top-level package. Otherwise the one top-level directory, or child of `src/`, that contains `__init__.py` and is not `tests` or `docs` is used. The changed files are split again with that name. A built-in library keeps the name already configured for it. When the checkout does not show exactly one package, the previous guess (the library name, hyphens turned into underscores) stays.

When a changed package file has no test file whose name matches it, test files in the nearest `tests` directory that mention that module are selected. This is the same kind of fallback the site-packages mapper already had, applied to a checkout, and it runs before the check gives up with "no tests could be mapped".

When pytest's `python_files` is `*` or `*.py`, a file in a test directory counts only if parsing it shows a test. A test is a function whose name starts with `test`, a class whose name starts with `Test`, a `TestCase` subclass, or a spec-style class whose name ends with `_` and that holds a method. A support module such as `tests/_support/branch/tasks.py`, which only defines plain functions, is not selected. The file is parsed and not executed.

No verdict rule changed.

## Why

A project can list its test dependencies in `dev-requirements.txt`, and tox can pull that file in with `-r`, without a file whose name starts with `requirements`. The setup-gap retry then does not recognise the missing distribution, so it is not installed.

The import name is not always the repository name with hyphens turned into underscores. A checkout whose package directory is `barcode/` was treated as `python_barcode`, so the changed files were not package files and no tests were mapped.

A changed module whose tests do not share its file name stopped at "no tests could be mapped", even when a test file next to it imports that module.

With `python_files = *`, every Python file under a test directory was treated as a test. Support files that define tasks, not tests, were selected in place of the real test module.

## Decision

- Treat every `*requirements*.txt` as a declared test-dependency source, except a system-package list whose name does not start with `requirements` (`system-requirements.txt` is an apt list). Follow `-r` and `--requirement` recursively from those files and from tox `deps`. Do not follow `-c` constraints.
- For a repository outside the built-in list, take the import package from the checkout once that checkout exists, and classify the diff again. Do not special-case a repository or a package name.
- After the stem match finds nothing for a changed package file, select up to the same per-file cap of test files in the nearest tests directory that mention the module.
- Under a catch-all `python_files` pattern, require a test function or a test class, found by parsing the file.

## Alternatives and tradeoffs

- Hard-coding one project's requirement filename, package directory, or support path would fix that project and miss the next one.
- Following every file under a `requirements/` directory would install files that are not requirement lists. Includes are followed only when a requirement file or tox `deps` names them.
- Installing every package in a tox docs environment pulls documentation packages, not only test packages. Tox `deps` is the list the project itself says to install for a test run, so the whole list is taken.
- Scanning every tests directory, not only the nearest, would map more files and would also run tests that belong to a different part of the tree. The nearest directory is the one the site-packages mapper already walks to.
- Treating every public function as a test under `python_files = *` would still select support files that define plain functions. Requiring a test function or a test class leaves those out, and also leaves out a project that keeps real tests as plain functions with neither a `test` prefix nor a spec-style class.

## What it means for you

A project that keeps test dependencies in `dev-requirements.txt` or behind tox `-r` gets those packages installed, and a missing one named by the error can be installed on the setup-gap retry. A package directory that is not the repository's name is the one the check uses, once the checkout is on disk. A change whose tests mention the module but do not share its file name still gets those tests. Support files under a catch-all pytest pattern are not run as tests.

## Offline proof

`tests/test_setup_sources_and_mapping.py` builds a temporary checkout for each rule: a `dev-requirements.txt` that includes another file, a cycle, a `..` include that is not followed, tox `deps` with `-r` and a direct name, the import package from a directory and from `setup.cfg` / `pyproject.toml`, the nearest tests directory, and a catch-all pattern whose support file has no test. Nothing from a live pull request is run.
