# The PR side installs its own dev extras; main's constraints never override a PR pin

## What changed

When a pull request is checked, the PR side's test extras are now read from the
PR checkout itself, not from main. Any requirement main declares as a test
extra is replaced by what the PR checkout declares. Packages the PR checkout
declares (runtime or extra) are removed from the main-side constraints file, so
main's frozen versions are never forced on top of a pin the project sets
itself. Main's side is unchanged.

## Why

On 6 Nov, loguru #1515 failed setup with a resolver conflict: main's freeze
pinned twine 7.0.0, while the PR's `loguru[dev]` pinned twine 6.2.0 exactly.
The PR deliberately lowered its own exact dev pins, so the conflict came from
our tooling forcing main's versions onto the PR, not from the PR.

## Decision

Each side installs its own declared dev extras. Main's constraints only cover
packages the PR checkout does not declare. No version is overridden on either
side.

## Alternatives and tradeoffs

- Loosen the PR's exact pin to a lower bound: rejected, it would change the
  project under test.
- Drop the constraints file entirely on the PR side: simpler, but loses
  reproducibility for packages the PR does not declare.

The cost is that the two sides can now differ in dev tool versions when the PR
changes them, which is what the PR intends.

## What it means for you

A pull request that changes its own dev pins now gets through setup. The
re-run of loguru #1515 installs twine 6.2.0 on the PR side and 7.0.0 on main,
and setup succeeds. (It is still could_not_verify for a separate reason, a
claim-extraction issue handled in another pull request.)
