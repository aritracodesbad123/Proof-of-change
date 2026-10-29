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
  rejected. See "Final figure" below for how many saved probes this affects.
- Weaker repairs could pass through a text fallback. That is why the fallback was removed: a repair that hides
  dropped keys in comments or strings and stores under a computed key is now rejected instead of passing.

## Follow-up: sys.modules stores are not keys

recorded_names no longer treats `sys.modules[...] = ...` as an observation key. That store installs a module, so a
probe that stubs a module this way can still have its keys read. Every other computed key stays unreadable, so a
repair that uses one is still rejected: `obs[name]`, `obs[key]`, `observations[obs_name + ...]`.

## Follow-up: original inputs from tokens, sys.modules in the original

- The original's inputs are now counted from the same tolerant token stream as its keys, not from the raw text. A
  loop inside a comment or a string (`# for x in [1, 2, 3, 4, 5]:`) no longer counts. Inputs read: a statement or
  comprehension loop over a literal list, tuple or set, or over range() with constant arguments, optionally wrapped
  in enumerate(), list(), tuple(), sorted() or reversed(). This matches what the repair's AST count reads.
- In the original's token count, `[ 'a.b' ] =` right after `sys . modules` is not a key, which matches recorded_names.
- A test checks that a comprehension cut from (1, 2, 3) to (1,) is rejected, so turning off comprehension input
  counting fails a test.

## Final figure

The test set is every distinct saved model-written probe from past runs: each file named model-*.py, deduplicated by the
sha1 of its bytes. Each probe gets a broken trailing line to stand in for the original, and the probe itself is used
as the repair. 55 of 679 would be rejected, all because they store under a key that cannot be read, such as
obs[name] or observations[obs_name + '.units']. No probe is rejected for fewer keys or fewer inputs.
