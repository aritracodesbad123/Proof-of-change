# Install a dev extra when no test extra exists, ground quotes loosely on study runs, and read a printed dict

## What changed

Three small changes. Nothing else in the product checks moved.

1. When a project has no extra named test, tests, or testing, the install also takes the `dev` extra, and any other extra that lists a module imported by `conftest.py`. A collection failure that is an ImportError or ModuleNotFoundError (including one raised while loading conftest) is a setup gap, so the existing install-and-retry runs. A new test that ran and then raised ModuleNotFoundError was already handled. A collection error produced no test result, so that retry never saw it.
2. Study runs ground claim quotes the same way product checks do: `grounded_claims(..., loose=True)`. A quote that is not found as written is compared again after paired Markdown marks are removed and dashes, arrows, and quotes are unified.
3. Study runs pass `literal_output=True` when they read a probe. A last line that is not JSON can be a Python literal `{'observations': {...}}`, read with `ast.literal_eval` and the same fail-closed rules as before.

## Why

The 2026-10-31 daily check recorded three failures that these changes cover.

- loguru pull request 1536. The project has no test extra. `freezegun` is listed in the `dev` extra, and `tests/conftest.py` imports it. Every pytest run exited 4 with `ModuleNotFoundError: No module named 'freezegun'`. The tests produced no results, so the missing module never went through the retry that installs a module named by a new test. Probes had already flagged one difference, so the verdict was needs attention and the setup-gap retry did not run.
- sqlparse pull request 941. Two claims were rejected with `source_quote not found in the PR text`. One quote dropped the backticks around the SQL and still used the same dash. The exact comparison rejected it. The loose comparison keeps it. The other quote changed double quotes to single quotes. The loose rules do not treat those as the same, so that claim stays rejected.
- toolz pull request 654. Both model probes exited 0 and were saved as `non-json output` on every run. That is what the parser records when the last line is a Python dict with single quotes, such as `print({'observations': {...}})`, and `literal_output` is off. With it on, that line is read. Values that are not JSON-shaped stay unparsed.

## Decision

- Prefer the extra named test, tests, or testing when one exists. Do not also install `dev` in that case.
- When none of those names exist, install every requirement in `dev`, and every requirement in an extra whose distribution name matches a top-level module imported by a `conftest.py` (`python-gitlab` matches `import gitlab`). The conftest files are parsed and not executed. The standard library is ignored. A dependency group is unchanged: only a group named test, tests, or testing is installed.
- Wheel metadata has no conftest. If it names no test extra, the install still requests `dev`.
- A collection import is a setup gap on a could-not-verify result and on a needs-attention result. The study retry reads the pytest summary already stored on the record, and for this gap it may install a requirement declared on main, including one that lives in an extra. If nothing safe is installed, a needs-attention verdict is left as recorded.
- Loose quote matching and literal probe output are on for study runs and product checks. The probe prompt, src-layout import rewrite, and the other product-only gates stay on product checks only. Callers that do not pass `loose` or `literal_output` still use an exact quote and JSON only.

## Alternatives and tradeoffs

- Installing every package in `dev` can pull documentation and type-checker packages, not only the one module conftest imports. That is the same choice as installing a test extra in full. Matching only the imported names would miss a `dev` extra whose import name and distribution name differ and that conftest does not mention.
- Leaving the collection error as needs attention whenever probes had already flagged something hid a missing install. Retrying it can change the test half of the verdict. If the retry cannot install anything, the recorded needs-attention verdict stays, so a probe finding is not replaced by a setup-gap line.
- Teaching the loose matcher to treat `'` and `"` as the same character would have kept the sqlparse claim that changed quote style. That matcher is shared with product checks and refuses different characters on purpose. This change only turns it on for study runs.
- Asking the model to print `json.dumps` is a separate prompt change and was not done. The parser accepts the dict print it already knows how to read safely.

## What it means for you

- A project whose tests import something from `dev`, and that has no test extra, gets that extra installed before pytest. If collection still fails on a missing module, the check installs the declared requirement and runs once more.
- More study-run claims survive when the only difference is Markdown or a dash. A quote that changes the words, or changes `"` to `'`, is still dropped, and the record says so.
- A study-run probe that prints a JSON-shaped dict with single quotes is scored. A tuple, a set, or an extra key is still `non-json output`.
