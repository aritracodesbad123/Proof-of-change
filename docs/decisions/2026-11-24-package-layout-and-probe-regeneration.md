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

When a probe is empty, or its code still does not parse after the parse repairs and the existing unusable
retry, it is discarded and one new probe is requested. The discarded code is saved as
`model-probes/<id>.rejected.py` and the model reply as `model-probes/rejected-reply.json`. That first failure
is not stored as a probe result, so it is not scored. The new probe goes through the same checks as any other
probe. If it is valid, the usual verdict rules decide. If it is still empty, still does not parse, or cannot
be run, the record stays could not verify. Tests that fail on the base and pass on the pull request do not
turn that record into verified. The rule that a verified result needs a model probe which ran a changed line
is unchanged.

## Why

Some projects keep the importable code under `src/` and use a second, private package directory next to the
public one. Only the public name was treated as the package, so a change in the private directory was filed
as "other". No test was mapped to it, and the check ran zero tests on each side.

A test module that the project collects by a path pattern was also missed: the pattern was compared with the
file name alone, so `testing/python/*.py` never matched `testing/python/fixtures.py`.

Treating every directory under `src/` as a package would have mapped testing and fixture trees as if they
were the library.

A probe that does not parse was repaired twice and then sent back once as unusable. When that answer still
did not parse, nothing was kept and the discarded text was not saved. Treating that failure as if it did not
matter, and verifying from the tests alone, would have marked a pull request verified without a probe that
ran. The AI-probe gate already refuses that, and it is left as it is.

## Decision

Discover package code from the path. Include `src/<package>/` and a top-level private package directory.
Exclude testing, fixture, and docs directory names. Match a `python_files` pattern that contains a slash
against the relative path.

After the existing repairs, regenerate once when every probe is empty or still does not parse. Keep the
discarded code and the reply. Judge the new probe with the existing gates. Do not verify when that probe
cannot be parsed or run.

Nothing here names a repository or a package. Nothing here rewrites a saved record. Replay does not re-map
tests and does not call the model; a later live run is what maps the previously skipped files and asks for
the new probe.

## Alternatives and tradeoffs

Guessing a single import name from the checkout still fails when two packages sit side by side, and the
configured name stayed the public one. Reading the path does not need the checkout, so the same split is
used when a pull request is chosen and again after the tree is checked out.

Matching every `python_files` pattern against the full path, including `test_*.py`, would still work, but
those patterns are file names. Only patterns that already contain a directory are matched as paths.

Sending the unparseable probe back more than once would spend more model calls. One regeneration is the cap.
Verifying from the tests when that regeneration also fails would have relaxed the AI-probe gate. It stays.

## What it means for you

A change under `src/` or in a private package directory is package code, and tests are mapped to it when the
project's pytest patterns name a matching test file. A change that only touches a testing or fixture
directory is still not package code.

An empty or unparseable probe is sent back once more, and the discarded text is kept under `model-probes/`.
If the new probe runs, it is judged like any other probe. If it does not parse or does not run, the check
stays could not verify even when the tests went from failing to passing.
