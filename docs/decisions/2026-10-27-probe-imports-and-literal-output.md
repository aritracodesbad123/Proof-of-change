# Model-written probes import the installed package, and a printed Python dict is read safely

Date: 27 Oct 2026

## What changed
On product checks only, two generic fixes for model-written probes (small scripts the AI writes to observe
behaviour on both sides of a pull request):

1. The probes prompt now tells the AI to import the package under test by its installed import name, never
   through the repository folder that holds the code. When the project uses a src layout (its code sits in a
   `src/` folder that is not itself a package), an import such as `from src.pkg import x` is rewritten to
   `from pkg import x` before the probe is frozen. An import of that folder that cannot be rewritten safely
   rejects the probe instead.
2. The prompt now says to print the last line with `json.dumps`. When a probe prints the observations as a Python
   dict instead (for example `{'observations': {'count': 0, 'ok': False}}`), the parser accepts it, but only in a
   narrow, safe form.

## Why
- In a src layout the `src/` folder is not on the import path, so a probe that imports `src.<package>` crashes with
  "No module named 'src'" on both sides and tests nothing.
- A probe that prints a Python dict uses `True`, `False`, `None` and single quotes, which are not JSON. The whole
  run was recorded as "printed no parsed output", although the observations were all there.

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

## Alternatives and tradeoffs
- Adding `src/` to the import path would run the checkout's files instead of the installed package, which can
  differ from what users get, so it was not chosen.
- Accepting any Python literal would hide changes, since a tuple and a list would look the same once saved. Only
  JSON-shaped values are accepted, so some probes still end as "printed no parsed output" when the AI ignores the
  prompt and prints other types.

## What it means for you
- Product checks lose fewer probes to these two crashes, so more claims are actually tested. A rewritten import is
  listed in the probe plan of the record.
- Study runs and the daily study are unchanged: same prompt, no rewrite, same parser.
