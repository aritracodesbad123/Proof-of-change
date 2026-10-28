# Parse repair counts read from the AST

Date: 2026-10-29

## Decision

The repair check compares observation keys and inputs before and after a parse repair. The repaired code parses, so
its counts are now read from its AST with recorded_names (#177). The broken original cannot be parsed, so it is still
read from its text.

- Keys in comments, docstrings and plain strings do not count. Keys in dead code also do not count: statements after
  an unconditional break, continue, return or raise, and `if False:` / `if 0:` bodies.
- A loop whose body breaks unconditionally counts as one input.
- range() with constant arguments counts its length, in both the text and the AST counts.
- An f-string key inside a loop over a readable iterable counts once per item.
- When the code stores under a key that cannot be read, the text count is used instead.

Each parse_repairs entry that got a reply now saves `counts`: before and after keys and inputs, and how each was
read (`ast` or `text`).

## Why

A repair could pass the text count by keeping dropped keys in a comment or in dead code. The AST count does not see
those keys.
