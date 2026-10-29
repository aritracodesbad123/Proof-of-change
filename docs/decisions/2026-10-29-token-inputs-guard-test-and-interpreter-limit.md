# Token-input guard test and the interpreter limit of parse repair

Date: 2026-10-29

## Decision

- A test covers the guard in `_token_inputs` that stops a list built by a comprehension (`[f(i) for i in data]`)
  being counted as a literal with one item. With the guard turned off, the test fails.
- Limitation, added to the README: the parse-repair step parses probe code with the Python that runs the check.
  Probes written in newer syntax, such as Python 3.14 template strings, do not parse on any Python older
  than 3.14 (3.11, 3.12 and 3.13 included). Nine saved
  markupsafe #512 probes fail this way. They are treated as parse errors and sent back for repair, and are
  rejected if they are never fixed.

## Why

Without the test, removing the guard would silently raise the original's input count, and honest repairs could then
be rejected. The interpreter limit is documented rather than fixed, because parsing with the probe's own target
Python would need that Python on the machine running the check.
