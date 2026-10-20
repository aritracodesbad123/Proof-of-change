# Every test failing on a missing module is not verified

## What changed

When every test fails on both sides with an import error (ImportError or ModuleNotFoundError), the verdict is could not verify. The reason says missing dependency. It is never verified.

## Why

The same failure on both sides used to count as a problem that already existed, which can be verified. A missing module means the tests never ran the change. That is not evidence that the change is fine.

## Decision

Use this only when every test that ran failed that way on both sides. A mix of passing tests and import errors stays on the old rule. An assertion error on both sides stays a pre-existing failure and can still be verified. A regression stays needs attention.

## Alternatives and tradeoffs

- Keep calling identical import errors verified. That treats a missing module as a passing check.
- Call any single import error could not verify. A suite that mostly passed would then lose a real result.

## What it means for you

If the whole run failed because a module was missing, the result says could not verify, with the reason missing dependency. Install the module and run the check again.
