# Comment-only and docs-only pull requests are verified

## What changed

On a product check, before any setup, the diff between the pull request's base and head commits is
classified from the code alone. The pull request text plays no part in this decision.

Every changed file must be one of these:

- A Python file whose syntax tree is the same on both sides. Comments are not part of the tree, so only
  comments changed.
- A documentation file that is not Python: `*.md`, `*.rst`, `*.txt`, or any non-`.py` file under a
  `docs/` folder. A `.py` file is always code, wherever it sits, including `docs/conf.py`.

When that holds, the verdict is verified with a plain reason that names each file and the changed line
numbers on the head side, for example: "Comment-only change: no code was altered. Comments changed in
pkg/m.py lines 2, 6." No sandbox, setup lookup or model call is made. The record carries
`fast_path: comment_only` and the report and PDF are produced as usual.

Docstrings count as code, because a program can read them through `__doc__`. If the only other
difference is in docstrings, the project's quick doc tests run in the Contree sandbox on the pull
request's code: doctests in the changed modules, plus tests that import those modules. If they pass, the
verdict is verified with the note "Documentation text only". If they fail, find nothing to run, or cannot
run, the normal check runs instead.

If the title or description says behaviour changed (a fix, a bug, a crash, something added, a changed
result) but only comments or docs changed, the verdict is needs attention: the pull request does not do
what it says. Wording about the text itself, such as "fix typo in comment", does not count.

Anything else falls through to the normal check unchanged: other file types (config, setup files,
tests), a file that does not parse, binary files, and new, deleted or renamed code files. A changed value
next to an unchanged comment, or text inside a string that is not a docstring, changes the syntax tree and
also takes the normal path.

The study route is unchanged, and so is the refusal when a required key is missing.

## Why

A pull request that only edits comments or documentation cannot change what the code does. Running the
full check on it spent minutes and often ended in could not verify or needs attention, which told the
reviewer nothing useful.

This supersedes the 22 October decision to keep the current behaviour for comment-only pull requests.
