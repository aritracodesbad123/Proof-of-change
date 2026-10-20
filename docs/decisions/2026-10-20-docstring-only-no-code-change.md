# A docstring or comment change is no code change

## What changed

A pull request that changes only docstrings or comments is recorded as no code change, with the reason docstring only. That is the same kind of result as a change that only touches type stubs.

## Why

Comments are not part of the program the checker compares, and docstrings are removed before that comparison. Calling the result verified said the behaviour had been shown to hold. Nothing was run that could show that, beyond the tests still passing.

## Decision

When the code is the same once docstrings are removed, and the tests do not need attention, the verdict is no code change. The reason names docstrings or comments. A regression is still needs attention. Each behaviour claim is marked as holding by construction. The coverage check and the AI-probe check only lower a verified result, so this result stays.

## Alternatives and tradeoffs

- Keep calling it verified. The report would say the change was shown to be safe when only the words changed.
- Skip the tests, as a typing-only change does. A docstring edit that also breaks a test would be hidden.

## What it means for you

A comment or docstring edit is reported as no code change, not as verified. If a test starts failing, the result is still needs attention.
