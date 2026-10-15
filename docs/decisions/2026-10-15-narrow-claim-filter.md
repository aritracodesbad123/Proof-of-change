# The test-notes filter now drops less

## What changed

The 14 Oct rule skips notes about a pull request's own tests and tools, so they are not read as promises about
behaviour. It was skipping too much, so it is now narrower in three ways:

1. A skipped "Testing" or "Verification" section now ends at the next bold label line (such as "- **Behavior**:"),
   a `<details>` block, a "Fixes #..." line, or the next ordinary sentence after the test list. Before, it ran on
   to the next heading and swallowed summaries and bug reports written after the test list.
2. A "nothing else changes" sentence ("other providers remain unaffected", "without affecting any current
   functionality") is never skipped, even inside a test section, unless it is about the tests or a tool.
3. A tool name (ruff, mypy, linter, ...) only causes a skip when it sits next to a word like run, pass, fail,
   check or output ("ruff check", "linting passes"). "Extend linter Fix to support creating files" is kept,
   because there the linter is the product. A sentence about a CI workflow or a `.yml` file is also kept, because
   the project's own automation is then the thing being changed.

## Why

A blind hand check on 40 pairs of agent-written and human-written pull-request descriptions found 17 product
sentences the rule threw away, all from agent-written pull requests (4 of them). Agent pull requests often put a
test list in the middle of the description, so a lopsided filter could make agent and human pull requests look
different for the wrong reason.

## Result on the same 40 pairs (used for tuning)

- Sentences skipped, agent side: 155 before, 94 after. Wrongly skipped: 17 before, 0 after.
- Sentences skipped, human side: 13 before, 11 after. Wrongly skipped: 0 before, 0 after.
- Promises found: unchanged (3 before, 3 after).
- The 17 sentences are now regression tests. They were used to tune this rule, so these numbers show the rule
  fixes what it was built to fix, not how it does on new pull requests.

## Result on 60 unseen pull requests (30 agent-written, 30 human-written)

- Sentences skipped, agent side: 80 before, 63 after. Human side: 43 before, 34 after.
- Promises found, agent side: 4 before, 5 after; the new one is a real promise. Human side: 2 before, 2 after.
- No new false promises.
- 3 real agent-side sentences are still skipped, just as before this change. Two of them (about the project's
  own lint workflow and linting rules) are now kept and added as tests, which brings the agent side to 61
  skipped with the same promises found. The third, inside a Testing section,
  is borderline.

## Known limit

- A list item that wraps onto a next line with no indent ends the test section early. That fails safe: the
  remaining test lines are kept and only reach the promise finder.

## Trade-offs

- Some boilerplate (links, sign-up blurbs) and a few borderline test notes, such as "test linter and LSP behavior
  for file creation", now reach the promise finder. They contain no promise words, so no extra promises appear.
