# Test names follow the project's pytest setting, and a pinned run stops when main moves

## What changed

The mapping from a changed source file to the test files that should run now reads the project's pytest
`python_files` setting. That setting is the list of file-name patterns pytest uses to decide which Python files
are test modules. It is read from the first of `pytest.ini`, `pyproject.toml`, `tox.ini` and `setup.cfg` that
pytest itself would use. When the project does not set it, the mapping uses pytest's own default,
`test_*.py` and `*_test.py`. A pattern that matches every file (`*` or `*.py`) counts a file as a test only
when it sits in a test directory, so a package module is not run as a test. `conftest.py` and `__init__.py`
are not test files, including when they sit in that test directory.

A line that sits inside a statement spanning several lines now counts as executable when changed-line coverage
is decided. coverage.py (the tool that records which lines ran) reports that whole statement on its first line,
so the change is counted on that first line. This applies on every route, not only a product check.

A run started with `--expect-commit` (or `POC_EXPECT_COMMIT`) checks that commit again before each pull
request, not only at the start. If main's head is no longer that commit, the run stops and says so in plain
words. It does not fetch and it does not move the checkout. The PDFs and the go/no-go summary are still written.

## Why

Two pull requests finished with no test matched to the files they changed. One of them names its tests with a
pattern other than pytest's default, written in its pytest config. The mapper only looked for `test_*.py` and
`*_test.py`, so it found nothing. The rule has to be the project's own setting, with no special case per
repository.

A change on a later line of a long statement (a call, a list or a dict written across several lines) was
dropped as non-executable, because coverage.py does not list that later line. A test or probe that ran the
statement could not be shown to have reached the change.

A run pinned to one commit kept going after main moved partway through. Later pull requests were then checked
with the new commit. Checking only at the start cannot see a move that happens after the first pull request.

## Decision

- Read `python_files` from the pytest config file, as a string or a list, and use those patterns both for a
  test file the change edits and for the file names searched from a source module's name. Fall back to
  `test_*.py` and `*_test.py` when the setting is absent. Do not add a case for any one repository.
- When deciding which changed lines are executable, map a line inside a multi-line statement to that
  statement's first line. Leave the verdict rules as they are: only the line numbers that go into them change.
- Before each pull request, read main's head. If it is not the commit the run was pinned to, stop with a
  plain-words reason and still write the PDFs and the go/no-go summary. A run that was not pinned still
  fast-forwards to `origin/main` once at the start, as before.

## Alternatives and tradeoffs

- Hard-coding the test-file pattern of one project would have fixed that project and missed the next one that
  uses a different pattern.
- Treating every Python file as a test when the pattern is `*` would have run the package's own modules as
  tests. Limiting that pattern to a test directory avoids that, and misses a project that keeps tests beside
  the code with no test directory and a catch-all pattern.
- Stopping at the first sign that main moved means the later pull requests are not checked in that run. They
  can be checked again on the new commit. Carrying on would mix two versions of this tool in one run.

## What it means for you

A project whose tests are not named `test_*.py` or `*_test.py` is mapped from the pattern in its pytest
config. A change inside a long statement counts toward changed-line coverage when that statement ran. A run
you pin with `--expect-commit` stops if main moves, and it still leaves a PDF for each check it finished and
a go/no-go summary that says why it stopped.

## Offline proof

`tests/test_python_files_and_commit.py` builds a tiny checkout for a custom `python_files` setting (in each of
the four config files), for the default when the setting is absent, and for a change on a later line of a
multi-line statement. `tests/fixtures/python_files/catch_all` is a checkout whose tests directory holds
`conftest.py`, `__init__.py`, and a real test module; the same test checks both `*` and `*.py`. It also pins a
run to one commit, moves main after the first pull request, and checks that the second is not run and that the
PDFs and the go/no-go summary are still written. Nothing from a live pull request is run.
