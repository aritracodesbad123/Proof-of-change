# Model-written probes import the installed package, a printed Python dict is read safely, and changed lines count at their statement's first line

Date: 27 Oct 2026

## What changed
On product checks only, three generic fixes. The first two are for model-written probes (small scripts the AI
writes to observe behaviour on both sides of a pull request); the third is for how changed lines are counted.

1. The probes prompt now tells the AI to import the package under test by its installed import name, never
   through the repository folder that holds the code. When the project uses a src layout (its code sits in a
   `src/` folder that is not itself a package), an import such as `from src.pkg import x` is rewritten to
   `from pkg import x` before the probe is frozen. An import of that folder that cannot be rewritten safely
   rejects the probe instead.
2. The prompt now says to print the last line with `json.dumps`. When a probe prints the observations as a Python
   dict instead (for example `{'observations': {'count': 0, 'ok': False}}`), the parser accepts it, but only in a
   narrow, safe form.
3. Each changed line is mapped to the first line of the statement that contains it before it is compared with
   coverage. This applies to the main-side lines used for probe coverage and to the pull-request-side lines used
   for test coverage.

## Why
- In a src layout the `src/` folder is not on the import path, so a probe that imports `src.<package>` crashes with
  "No module named 'src'" on both sides and tests nothing.
- A probe that prints a Python dict uses `True`, `False`, `None` and single quotes, which are not JSON. The whole
  run was recorded as "printed no parsed output", although the observations were all there.
- coverage.py (the tool that records which lines ran) reports a statement that spans several lines only at its
  first line. A change on a later line of a long list, dict or call, such as one entry of a multi-line list of
  regular expressions or a new entry inserted into a multi-line dict, was therefore counted as non-executable and
  dropped. A probe or test that really ran that statement could not be shown to reach the change.

## Decision
- The src layout is detected from the base-side checkout only: a `src/` folder without its own `__init__.py`,
  whose child packages or modules are the names that may be rewritten. Nothing is hardcoded per project.
- The rewrite is done on the parsed code, statement by statement, and only when the import is the whole statement
  on its own lines. It covers `from src.pkg... import ...`, `from src import pkg` and `import src.pkg... as m`.
- It fails closed. A bare `import src`, `import src.pkg` without an alias, a name that is not in the `src/` folder,
  an import sharing a line with other code, or any use of the name `src` left after the rewrite rejects the probe
  with a reason in the record.
- The Python-dict output is read with `ast.literal_eval` (it is never run). It is accepted only when the last line
  is exactly `{'observations': {...}}` and every value is something JSON can hold unchanged: strings, finite
  numbers, true, false, null, lists and dicts with string keys. Anything else, such as an extra key, a tuple, a set,
  bytes, a non-string key or an object's printout, stays unparsed and is recorded as before. The usual output
  contract (size cap, number and length of names, exit code) still applies.
- Statements are found with Python's own parser (the AST). A line maps to the innermost statement whose line range
  holds it, so a line inside the body of an `if` or a function keeps its own statement, and a line of a multi-line
  header maps to that header. Lines outside every statement, such as comments between statements, stay as they
  are. If the file cannot be parsed, the lines are left unchanged, so nothing is credited that the plain diff did
  not already name. A pure insertion is still judged by the main lines just before and after it; those lines are
  mapped the same way.

## Alternatives and tradeoffs
- Adding `src/` to the import path would run the checkout's files instead of the installed package, which can
  differ from what users get, so it was not chosen.
- Accepting any Python literal would hide changes, since a tuple and a list would look the same once saved. Only
  JSON-shaped values are accepted, so some probes still end as "printed no parsed output" when the AI ignores the
  prompt and prints other types.

## What it means for you
- Product checks lose fewer probes to these two crashes, so more claims are actually tested. A rewritten import is
  listed in the probe plan of the record.
- A change inside a multi-line statement can now count as reached when the statement ran.
- Study runs and the daily study are unchanged: same prompt, no rewrite, same parser, same changed-line counting.
