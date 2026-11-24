# Package directories and one more probe

## What changed

A changed Python file counts as package code when it lives in the named package, in a `src/` layout, or in a
private package directory (a directory whose name starts with an underscore, such as `src/_impl`). The tests
for that file are then mapped the same way as for any other package file.

A directory named `tests`, `test`, `testing`, `fixtures`, `fixture`, `testdata`, `docs`, or `doc` is not a
package. That is true under `src/` and when the name itself starts with an underscore (`src/_fixtures`). A
file named `fixtures.py` inside a real package is still package code. The directory is what is skipped, not
every file whose name contains "fixtures".

A project's pytest `python_files` pattern that includes a directory, such as `testing/python/*.py`, is matched
against the path of the file, not only against the file name. The stem of the changed package file can then
find that test module. A pattern with no directory still matches the file name only.

## Why

Some projects keep the importable code under `src/` and use a second, private package directory next to the
public one. Only the public name was treated as the package, so a change in the private directory was filed
as "other". No test was mapped to it, and the check ran zero tests on each side.

A test module that the project collects by a path pattern was also missed: the pattern was compared with the
file name alone, so `testing/python/*.py` never matched `testing/python/fixtures.py`.

Treating every directory under `src/` as a package would have mapped testing and fixture trees as if they
were the library.

## Decision

Discover package code from the path. Include `src/<package>/` and a top-level private package directory.
Exclude testing, fixture, and docs directory names. Match a `python_files` pattern that contains a slash
against the relative path.

Nothing here names a repository or a package. Nothing here rewrites a saved record. Replay does not re-map
tests; a later live run is what maps the previously skipped files.

## Alternatives and tradeoffs

Guessing a single import name from the checkout still fails when two packages sit side by side, and the
configured name stayed the public one. Reading the path does not need the checkout, so the same split is
used when a pull request is chosen and again after the tree is checked out.

Matching every `python_files` pattern against the full path, including `test_*.py`, would still work, but
those patterns are file names. Only patterns that already contain a directory are matched as paths.

## What it means for you

A change under `src/` or in a private package directory is package code, and tests are mapped to it when the
project's pytest patterns name a matching test file. A change that only touches a testing or fixture
directory is still not package code.
