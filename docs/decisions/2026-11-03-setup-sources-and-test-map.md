# Requirement files, the import package, and which files are tests

## What changed

Plain `requirements.txt` is still a test dependency, as it was before. Any other requirements file is a test dependency only when its name contains `test` or `dev`, in any case. That covers `dev-requirements.txt`, `requirements-test.txt` and `test_requirements.txt`. It does not cover `docs-requirements.txt` or `requirements-lint.txt`. A line `-r` or `--requirement` in a file that is already followed, and the same line in a tox `deps` setting, is followed, including when the included file includes another. A lint or docs file is read when one of those lines names it, and not otherwise. A cycle stops. A path with `..`, a URL, or a path that leaves the project is not followed. Those lines are declared test dependencies: they are installed with the other requirement files, and the setup-gap retry can see them. The dependencies-only install uses the same filename rule. The check that finds an aggregate requirements file, or a file that only pins lint tools, still looks at every top-level `requirements*.txt`, so a component app is unchanged.

For a repository that is not one of the built-in libraries, the import package is read from the checkout. `packages` and `package-dir` in `setup.cfg` or `pyproject.toml` win when they name a single top-level package. Otherwise the one top-level directory, or child of `src/`, that contains `__init__.py` and is not `tests` or `docs` is used. The changed files are split again with that name. A built-in library keeps the name already configured for it. When the checkout does not show exactly one package, the previous guess (the library name, hyphens turned into underscores) stays.

When a changed package file has no test file whose name matches it, test files in the nearest `tests` directory that mention that module are selected. This is the same kind of fallback the site-packages mapper already had, applied to a checkout, and it runs before the check gives up with "no tests could be mapped".

When pytest's `python_files` is `*` or `*.py`, a file in a test directory counts only if parsing it shows a test. A test is a function whose name starts with `test`, a class whose name starts with `Test`, a `TestCase` subclass, or a spec-style class whose name ends with `_` and that holds a method. A support module such as `tests/_support/branch/tasks.py`, which only defines plain functions, is not selected. The file is parsed and not executed.

No verdict rule changed.

## Why

A project can list its test dependencies in `dev-requirements.txt`, and tox can pull a file in with `-r`, without that file's name starting with `requirements`. The setup-gap retry then does not recognise the missing distribution, so it is not installed. Reading every file whose name contains `requirements` also installs documentation and lint pins that the tests do not need.

The import name is not always the repository name with hyphens turned into underscores. A checkout whose package directory is `barcode/` was treated as `python_barcode`, so the changed files were not package files and no tests were mapped.

A changed module whose tests do not share its file name stopped at "no tests could be mapped", even when a test file next to it imports that module.

With `python_files = *`, every Python file under a test directory was treated as a test. Support files that define tasks, not tests, were selected in place of the real test module.

## Decision

- Keep plain `requirements.txt` as a test dependency. Also take a requirements file whose name contains `test` or `dev`, ignoring case. Do not take `docs-requirements.txt` or `requirements-lint.txt` unless a followed file or tox `deps` includes it with `-r` or `--requirement`. Follow those includes recursively. Do not follow `-c` constraints. Leave the aggregate and lint-pin scan on `requirements*.txt`.
- For a repository outside the built-in list, take the import package from the checkout once that checkout exists, and classify the diff again. Do not special-case a repository or a package name.
- After the stem match finds nothing for a changed package file, select up to the same per-file cap of test files in the nearest tests directory that mention the module.
- Under a catch-all `python_files` pattern, require a test function or a test class, found by parsing the file.

## Alternatives and tradeoffs

- Hard-coding one project's requirement filename, package directory, or support path would fix that project and miss the next one.
- Treating every `*requirements*.txt` as a test dependency installs documentation and lint pins. Limiting the name rule to `test` and `dev`, and still following `-r`, installs a lint file only when the project points at it.
- Following every file under a `requirements/` directory would install files that are not requirement lists. Includes are followed only when a requirement file or tox `deps` names them.
- Installing every package in a tox docs environment pulls documentation packages, not only test packages. Tox `deps` is the list the project itself says to install for a test run, so the whole list is taken.
- Scanning every tests directory, not only the nearest, would map more files and would also run tests that belong to a different part of the tree. The nearest directory is the one the site-packages mapper already walks to.
- Treating every public function as a test under `python_files = *` would still select support files that define plain functions. Requiring a test function or a test class leaves those out, and also leaves out a project that keeps real tests as plain functions with neither a `test` prefix nor a spec-style class.

## What it means for you

A project that keeps test dependencies in `dev-requirements.txt`, or behind tox `-r`, gets those packages installed, and a missing one named by the error can be installed on the setup-gap retry. A docs or lint requirements file is not installed unless something includes it. Plain `requirements.txt` is still installed. A package directory that is not the repository's name is the one the check uses, once the checkout is on disk. A change whose tests mention the module but do not share its file name still gets those tests. Support files under a catch-all pytest pattern are not run as tests.

## Offline proof

`tests/test_setup_sources_and_mapping.py` builds a temporary checkout for each rule: a `dev-requirements.txt` that includes another file, a cycle, a `..` include that is not followed, tox `deps` with `-r` and a direct name, `docs-requirements.txt` and `requirements-lint.txt` left unread, the lint file read when tox `deps` points at it, plain `requirements.txt` still read, the import package from a directory and from `setup.cfg` / `pyproject.toml`, the nearest tests directory, and a catch-all pattern whose support file has no test. Nothing from a live pull request is run.
