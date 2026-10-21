# Test both versions of an unreleased companion package, and stop slow example shrinking

## What changed

1. **Unreleased companion package.** Some projects depend on a companion package whose matching release does not
   exist yet, and say in their own settings which exact git commit of it to use. When we see that, we now test the
   pull request twice:
   - once with the companion package that a normal install chooses, on both sides, and
   - once more after installing that exact commit on the pull request side only (checked against the install
     record). The base side keeps the release the normal install chose.
   Both results are in the report. The final result is "needs attention" if either run needs attention, and
   "verified" only if both are verified.
2. **Time cap for property tests.** Projects that use Hypothesis (a tool that tries many random inputs) now run
   without its "shrinking" step, the step that searches for the smallest failing input. All the project's other
   settings stay the same, on both sides. When a run still hits the time limit, the report now names the first error
   seen before the cut-off.

## Why

On 14 Oct a pyjanitor pull request needed functions that only exist in an unreleased version of its companion
package. A normal install failed 112 tests, while the pinned commit failed 4 of the PR's own new tests. Testing only
one of the two hides half of that picture. One run also took the full 15 minutes because Hypothesis spent the time
shrinking the same error over and over, so the report only said "timed out".

Installing that pinned commit on the base side as well made the base tests fail to load. The base code is written
for the released companion, and the unreleased pin does not provide what those tests import. The pin is what the
pull request needs, so only the pull request side gets it. The base side stays on the release.

## Trade-offs

- Pull requests with a pinned companion take about twice as long.
- The second run does not use the same companion on both sides. A difference there can come from the companion
  version as well as from the pull request. That is the comparison the project asks for: new code with the pinned
  companion, against the base on the released companion. The first run still compares both sides on the release.
- Without shrinking, a failing example in the logs can be larger and harder to read. Whether a test passes or fails
  does not change.
