# A narrow cross-run can settle a differs claim

## What changed

A cross-run is a test the pull request added or edited that fails on the base (the old code) and passes on the pull
request (the new code). When that happens, the check may treat a claim that says behaviour changes (a "differs"
claim) as proven. It may do that only when every probe of that claim agreed, meaning the old and new code returned
the same value on the probe's inputs, or when that claim's probes never ran.

The rule never verifies a record that has any of these:

- a claim that says the result stays the same, whose behaviour was seen to differ
- a behaviour difference that no claim covers
- a crash on the pull-request side
- a test that fails on the pull request, including one that already failed on the base

If the pull request did not add or edit a test that fails on the base and passes on the pull request, there is no
cross-run and the verdict is unchanged. A new test that was never run on the base (it is absent there and only
passes on the pull request) is not a cross-run.

## Why

A differs claim whose probes all returned the same value was scored as "does not differ although the claim says it
does", so the check was needs attention, or could not verify when the probe never reached the change. The pull
request's own new or changed tests can show the change: they fail on the old code and pass on the new code. That is
real evidence for the differs claim the probes did not show.

It is not evidence that the rest of the record is fine. A loose reading, which treated a passing cross-run as enough
to verify the record, verified dask pull request 12645 and rich pull request 4147. Both are true catches. On dask
12645 a claim that said a result would stay the same was seen to change. On rich 4147 a behaviour changed that no
claim covers. The loose form was rejected.

## Decision

- The rule runs at the end of the verdict, after the tests and the probes have been judged. It can only raise a
  held-back verdict to verified. It never lowers a verdict.
- A test counts toward the cross-run only when it is in the comparison's fixed list (failed on the base, passed on
  the pull request) and it lives in a test file the pull request adds or edits. Nothing in the rule names a
  repository or a pull request.
- A differs claim is settled only when every observation linked to it agreed, or the claim matched no observation
  (its probes never ran). A claim whose probes did not all agree, including one probe that raised the same exception
  on both sides, is left alone.
- The four exclusions above block verification even when the differs claim itself would qualify. An unclaimed
  difference includes one that is only shown as advisory. A crash includes a probe that crashed or timed out on the
  pull-request side.
- The reason names the settled claims and says the new or changed tests fail on the base and pass on the pull
  request. The flag is `cross_run_settled`.

Held out, on its own, this rule settles 6 of 9 false alarms and 5 of 10 abstentions. No true catch flips. The two
known misses, mlxtend pull request 1229 and skrub pull request 2319, are still missed: what was wrong in them is
unclaimed behaviour, and this rule does not turn unclaimed behaviour into a catch. Altair pull request 4204 and
pingouin pull request 545 have no new tests, so the rule does not apply to them.

## Alternatives and tradeoffs

- The loose form would verify whenever the cross-run passed. It was rejected because it verified dask 12645 and
  rich 4147, both true catches.
- Treating every new passing test as a cross-run would count tests that were never run on the base. Those tests did
  not fail on the old code, so they are not this evidence.
- Using the cross-run to explain away a contradicted same claim, an unclaimed difference, a pull-request crash, or a
  failing test would hide a real problem behind one passing test. Those records stay not verified.
- Not settling a claim whose probes never ran would leave the abstentions that are only "no observation matched" as
  could not verify, even when the new tests fail on the base and pass on the pull request.

## What it means for you

A check whose only problem was a differs claim the probes did not show, and whose new or changed tests fail on the
base and pass on the pull request, can now come out verified. The reason says the cross-run settled that claim. A
check with a contradicted same claim, an unclaimed difference, a crash on the pull request, or a failing test stays
not verified. A check with no new or changed tests is unchanged.

## Offline proof

The fixtures under `tests/fixtures/narrow_cross_run/` are synthetic records, trimmed to what the verdict reads.
`dask-12645.json` and `rich-4147.json` are modelled on those two pull requests: both pass the cross-run, and both
stay not verified. `agreeing-settled.json` is the false alarm the narrow rule does settle: the probes agreed, the
cross-run passed, and nothing else is wrong, so the verdict is verified. `never-ran-settled.json` is the same for a
differs claim whose probes never ran. There is one fixture for each exclusion (a same claim that differed, an
unclaimed difference, a crash on the pull-request side, and a test that fails on the pull request), plus fixtures
where there is no cross-run and where the probes did not all agree. `tests/test_narrow_cross_run.py` re-judges them.
Nothing from the pull requests is run again.
