# A missing probe does not cancel tests that already prove the fix

## What changed

A verified result is no longer lowered to "could not verify" only because the AI-written probe is missing, empty, rejected, crashed, or never ran a changed line, when the pull request's own tests already prove the fix. Proof means a new or changed test that fails on the base and passes on the pull request on every recorded run.

That proof does not include a test that also passes on the base, a failure that is only an environment, setup or collection error, a test this platform skipped, or a renamed test. A platform skip is recorded as not visible on this platform.

An adequate probe that contradicts a claim, a regression, or a failure on the pull-request side still blocks verified. Changed lines that coverage measured and found unrun still block verified. A probe whose every input raises on both sides is not adequate and is not treated as "unchanged". Probe inputs are seeded from literal arguments in the base source and from formatter round-trips such as `parser(value.isoformat())`.

A claim that only describes the old behaviour is not typed as expecting the two sides to match; it is checked on the base side only. A claim that the result is "the same as" or "behaves like" something else is checked on the pull-request side only and does not need attention by itself. An unbound "untouched" or "unchanged" claim with no observation does not cancel test proof. An adequate probe that contradicts a claim still does.

Saved records are not rewritten. A verdict changes only when that record is re-judged.

## Why

The AI-probe gate treated a missing probe as evidence that the change was not exercised, even when new tests failed on the old code and passed on the new code. That hid fixes. Relaxing the gate on its own would also have let real breaks through, where the tests did not really prove the fix, the probe never reached the branch, or a claim was typed as "same" when it was not a comparison of the two sides.

## Decision

- The absence of a usable probe is neutral. It neither proves nor disproves a fix.
- Test proof is the fail-then-pass set above, and nothing weaker.
- Coverage of changed lines still applies first. Zero covered lines stays "could not verify".
- Probes that raise on every input are not adequate and are not "unchanged".
- The claim rules above are generic. Nothing is special-cased to a repository or a pull request number.

## Alternatives and tradeoffs

Leaving the gate as it was keeps real breaks out, and also keeps proven fixes at "could not verify". Treating every new passing test as proof would count tests that already passed on the base and tests that only failed because the environment could not collect them. Using a probe that raised on every input as "unchanged" would say the behaviour held when the probe never reached it.

## What it means for you

A check whose tests fail on the base and pass on the pull request can come out verified even when no AI probe ran, as long as nothing else contradicts the claim and the changed lines were exercised. A check with a real contradiction, a regression, or changed lines that never ran stays not verified. Re-judging an old record applies the new rule; the stored file is not edited by this change.
