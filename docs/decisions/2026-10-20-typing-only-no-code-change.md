# A typing-only pull request is recorded as no code change

## What changed

A pull request is recorded as no code change only when every file it changes is a `.pyi` stub or a `py.typed` marker. A `.pyi` file is a type stub: it describes types and does not run. `py.typed` is a marker file that says a package ships type information.

When that rule applies, the behaviour checks are not run. The result is still one of the three existing verdicts: could not verify, because nothing was checked. The record also stores `no_code_change` as true and `no_code_change_reason` as `typing_only`, so those cases can be counted apart from other could-not-verify results.

Any other file keeps the pull request on the normal checks. That includes a `.py` file whose only edits are type hints, a `.pyi` file together with a `.py` file, and a stub or marker together with a readme or any other file. The rule looks at file names only. It does not read the diff to decide that a `.py` edit is "only hints".

An empty diff, and a diff that changes no Python or compiled code in the package, still uses the existing skip. The pull request is not tested, and the skip reason stays "no Python/compiled code in the package (docs, CI or tooling only)".

## Why

Stubs and the `py.typed` marker do not change what the package does when it runs. Sending them through the behaviour checks spends a run on files that cannot change behaviour, and the result looks like any other could-not-verify, with no field a later count can use.

A `.py` file can still change what runs even when the visible edit is only a type hint, because the same file holds the code that runs. Those pull requests stay on the normal checks.

## Decision

- Apply this rule only when the list of changed files is not empty and every file is a `.pyi` stub or a file named exactly `py.typed`.
- On that record, set `no_code_change` and `no_code_change_reason: typing_only`, set the verdict to could not verify, and say that behaviour was not checked.
- Do not run the behaviour checks for that record.
- Leave every other diff, including a `.py` file with only hint edits, on the normal checks, with no change to how those checks decide.
- Leave an empty diff and a non-Python diff on the existing skip.
- A study score still accepts the record. The model was not called because there was no behaviour to check. A record that did not call the model for any other reason is still refused.

## Alternatives and tradeoffs

Treating every hint-only edit as no code change would also skip `.py` files. Those files can change what runs, so the rule does not inspect the diff text.

Adding a fourth verdict would change how results are scored. The three verdicts stay as they are, and the countable label lives in `no_code_change_reason`.

Skipping a typing-only pull request the same way a docs-only pull request is skipped would leave no record, so the cases could not be counted.

## What it means for you

A pull request that only adds or edits `.pyi` files or `py.typed` markers is recorded as could not verify, with `no_code_change_reason` set to `typing_only`, and the behaviour checks are not run. A pull request that also changes any other file, including a `.py` file that only gains type hints, is checked exactly as before. A pull request with an empty diff, or with no Python or compiled code in the package, is still skipped with the same reason as before.
