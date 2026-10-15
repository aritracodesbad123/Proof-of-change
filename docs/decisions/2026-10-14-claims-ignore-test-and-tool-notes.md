# Notes about tests or tools are not promises about behaviour

## What changed

When a pull request's description says something "stays unchanged", we treat it as a promise that needs its own
check. That rule now skips three kinds of text that are not promises about what the code does:

1. A sentence that describes the tests the pull request adds ("Add tests for ... untouched columns and unchanged
   inputs").
2. A sentence about a checking tool's output (mypy, ruff, linters, type checkers: "its output is identical").
3. Lines under a "Test plan", "Testing" or "Type checking" heading.

## Why

Two clean pull requests on 14 Oct were marked "could not verify" only because of such sentences. The words
"unchanged" and "identical" were about what the tests cover or what a type checker printed, not about the
program's results.

## Trade-offs

- A real promise written inside a test plan, or in the same sentence as a tool's name, is now missed by this rule.
  The project's tests and the AI-written probes still run. Checked on every PR from 14 Oct: only those two notes
  and one test-description line in another PR were dropped; every other promise is still found.
