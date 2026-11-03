# A flagged claim needs attention even when no tests were collected

## What changed

When a probe flags a claim and neither side collected a test, the verdict is now needs attention. The reason names
the flagged claim and says that no tests ran. Before this, that case returned could not verify, so the flag was
hidden.

A record whose probes are not flagged still stays could not verify when nothing was collected. A differs claim
whose only probe used inputs where both sides agree, because the probe never reached the change, also stays could
not verify. That exception is unchanged, including when nothing was collected.

## Why

The check used to return could not verify as soon as `nothing_collected_both` was true, before a flagged claim
could raise the verdict. An empty test run then hid a claim the probe had already flagged. Collecting nothing is
not evidence that the flag is harmless.

## Decision

- A red or amber probe observation (a claim that was contradicted, a differs claim that was not shown, or a
  difference no claim covers) makes the verdict needs attention even when no test was collected on either side.
- The reason is `needs attention: flagged claim(s) <id>; no tests ran (<the tests' own reason>)`. An observation
  with no claim id is named by its observation name instead.
- The agreeing-inputs exception is not part of this change. When every flagged observation is "does not differ"
  for a differs claim, and every one of those probes is marked unable to reach the change, the verdict stays
  could not verify, with the same reason as before.
- Nothing else in the verdict order changes. A probe that is not flagged still cannot raise the verdict.

## Alternatives and tradeoffs

- Leaving the old return hides a real flag behind an empty collection. The flag is the finding.
- Also raising needs attention for a probe that never reached the change would treat "both sides agree, and the
  probe never passed the new argument" as a pull-request finding. That case stays could not verify.
- Dropping the tests' own reason from the sentence would hide why collection failed. It stays in parentheses.

## What it means for you

A check that collected no tests, and whose probe flagged a claim, now says needs attention and names that claim.
A check that collected no tests and whose probes did not flag anything still says could not verify.

## Offline proof

`tests/fixtures/gate_order/flagged-nothing-collected.json` is a claim that says the result stays the same, while
the probe shows it changed, and neither side collected a test. The verdict is needs attention, and the reason
names C1 and says no tests ran. The same holds when the tests' reason is the "no results on both sides" line.

`tests/fixtures/gate_order/clean-nothing-collected.json` is the same claim with both sides agreeing, and nothing
collected. The verdict stays could not verify.

These existing fixtures keep their verdicts:

- dask pull request 12645: needs attention, not settled by the cross-run
- rich pull request 4147: needs attention, not settled by the cross-run
- python-barcode pull request 162, with and without a passing cross-run: needs attention, not settled

`scripts/rejudge_gate_order.py` reads a directory of `record.json` files and prints, for each, the stored verdict
and the verdict under this code, then lists the ones that move. Printed paths are relative to that directory.
84 stored `record.json` files in this repository were considered. None is a flagged claim with nothing collected
and a stored verdict other than needs attention, so none moves because of this rule. A full re-judge can still
differ from a stored verdict when a later rule landed after the record was written. Nothing from a pull request
is run again.
