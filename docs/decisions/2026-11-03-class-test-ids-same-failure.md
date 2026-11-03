# Class-style test ids, and a same failure does not block a cross-run

## What changed

Two changes to the narrow cross-run rule (the rule that can settle a differs claim from a test the pull request
added or edited, when that test fails on the base and passes on the pull request).

A test id written with dots, such as `tests.x.TestCls::t`, was turned into the path `tests/x/TestCls.py`. The
class name was treated as a folder, so the id never matched the test file the pull request edited
(`tests/x.py`). The module path is now the longest prefix of that dotted name that is a real `.py` file. The
rest stays as classes and the test name, so the id becomes `tests/x.py::TestCls::t`. A nested class
(`Outer.Inner`) stays as `Outer::Inner`. A parameter id stays on the test name (`t[a.b]`). A plain function
`tests.x::test_fn` becomes `tests/x.py::test_fn`. When the checkout is not mounted, a path in the pull request's
file list counts as a real file. When no prefix is a real file, the old dot-to-slash path is kept.

The failing-test exclusion is narrower. A test that fails the same way on the base and on the pull request no
longer blocks the cross-run. Same way means the same outcome on every repeat, and the same exception type after
side-path normalisation (the same folder-name cleanup used when probe output is compared: side-main and
side-pr, and the same pair for venv, cwd, home and out). A message that names no exception type still blocks,
because the type was not shown. These still block:

- a regression, which passes on the base and fails on the pull request
- a new test that fails on the pull request, or a test in a file the pull request edits that fails there
- a test that is unstable on the pull request, meaning its repeats do not agree

The other exclusions are unchanged: a same claim whose behaviour was seen to differ, a difference no claim
covers, and a crash on the pull-request side.

The real-run settled count is 0 so far. No live check was run. Stored records do not carry the exception type
of a failure that already failed on both sides, so none of them settle because of this change.

## Why

Pytest's report names a test method as `module.Class::test`. Replacing every dot with a slash made the class
look like a file that does not exist, so a new or changed test in that class was invisible to the cross-run.

A test that already fails on the base, with the same exception on the pull request, is not news about this
change. Blocking the whole record on it hid a cross-run that did show the change. A test the pull request
itself added or edited, a test that newly fails, and a test whose pull-request repeats disagree are still news,
and they still block.

## Decision

- Resolve the module by checking which dotted prefix is a real `.py` file, longest prefix first, including a
  package `__init__.py` when there is no sibling `.py` file. Do not look at the process's current directory.
- Keep a same-outcome failure from blocking only when every run on both sides names one and the same exception
  type after side-path normalisation, and the test does not live in a file the pull request adds or edits.
- Leave the other three exclusions, and the rule that one fixed test can settle every qualifying differs claim,
  as they are.

## Alternatives and tradeoffs

- Always stripping the last dotted part would treat a real module named `TestCls.py` as a class. Checking which
  prefix is a file avoids that, and it misses a class when a longer module file of the same name also exists.
- Treating every pre-existing failure as harmless would let an edited test that still fails, or a failure whose
  exception type changed, settle a claim. Those stay not verified.
- Comparing the whole message, not the exception type, would block a failure whose text differs only by a line
  number. The type is what this rule compares, after the side folders are removed.

## What it means for you

A differs claim the probes did not show can now be settled when the only failing tests are ones that already
failed the same way on the base, outside files the pull request edits. A regression, a new or edited test that
fails, or a test whose pull-request repeats disagree still keeps the record not verified. dask pull request
12645, rich pull request 4147, and the modelled barcode pull request 162 stay not verified. The real-run
settled count is 0 so far.

## Offline proof

`tests/test_test_id_module.py` checks the class, nested-class, plain-function and parametrised forms against a
real `.py` file, and checks that the longest real file wins. The fixtures under
`tests/fixtures/narrow_cross_run/` add one record for each blocker (a regression, a new test that fails, an
edited test that fails the same way, a pull-request-unstable test, and a different exception type) and one
record where the same failure on both sides does not block. `dask-12645.json`, `rich-4147.json`, and
`tests/fixtures/same_input_guard/barcode-162.json` stay not verified. `tests/test_narrow_cross_run.py` and
`tests/test_same_input_guard.py` re-judge them. Nothing from those pull requests is run again.
