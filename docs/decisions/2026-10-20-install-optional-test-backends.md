# Optional test backends install when they can

## What changed

Packages declared by a project's test extra (other than pytest and the project itself) are installed when that is possible. If one of them fails to install, it is skipped and the others are still tried. A skipped backend does not fail the environment and does not by itself decide a verdict.

## Why

A test extra often lists an optional backend next to the test runner. Installing the whole extra as one step meant one backend that cannot be built stopped the entire environment, so no tests ran.

## Decision

Try the extra as a group first when that is how the environment is built. If that group fails, install each optional backend on its own and record which ones were skipped. A checkout whose test extra fails is installed again without that extra, and the backends are then tried one by one. When the project declares no such backend, the install commands stay as they were.

## Alternatives and tradeoffs

- Keep failing the environment when any optional backend fails. Tests then do not run at all.
- Ignore test extras. Runs would miss backends the project itself says its tests use.

## What it means for you

A missing optional backend is recorded as skipped. The rest of the environment still comes up. Whether a missing module changes the verdict is a separate rule.
