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

## Follow-up: tokens for the original, no text fallback for the repair

- The broken original's keys are now counted from its tokens (tokenize). When a line can't be tokenized, it is skipped
  and tokenizing goes on from the next line. Only dotted string keys in key positions count: right after `{` or `,`
  and followed by `:` (a dict key), or between `[` and `] =` (a subscript store). Comments, docstrings and other
  strings, such as import_module('pkg.mod') or mock.patch('pkg.mod.f'), do not count. Line breaks alone do not change
  the count.
- The repair is read from its AST only. When its keys can't be read (k = 'f.a'; o[k] = 1), the repair is rejected.
  There is no fallback to the text count.
- Inputs in the AST now also count comprehensions over a readable iterable, as the text count does.

## Risks

- Honest repairs can be rejected when the two counts disagree, because the original is read from tokens and the
  repair from the AST. Repairs that store under a computed key (obs[name] = ..., sys.modules[name] = ...) are always
  rejected. On the saved probes, 53 of 607 distinct probes would be rejected this way if they were the repair.
- Weaker repairs could pass through a text fallback. That is why the fallback was removed: a repair that hides
  dropped keys in comments or strings and stores under a computed key is now rejected instead of passing.
