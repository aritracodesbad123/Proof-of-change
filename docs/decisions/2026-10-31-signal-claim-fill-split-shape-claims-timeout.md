# Blank claim lists filled from the probe's own names, a split raise counted as one shape, and one claims retry

## What changed

Three small changes, from the re-run of the study checks. Nothing else in judging or probe writing moved.

1. After the probe retry still leaves `claims` empty, a study run fills that list from the claims the probe already names. A name counts when it is in the probe's description, when the probe id ends in it (`probe-c1` is claim C1, `probe1` is not), or when the code records an observation that starts `c1_` or `c1.`. Only those known claims are attached. Each keeps the expectation the claims step recorded. The cover is the prefix the code actually records (`c1_*` or `c1.*`).
2. A probe that records a raise on one observation and the returned value on a sibling is one raise-to-value shape. `c1_exception` (main raises IndexError, the pull request is absent) together with `c1_result` (main is absent, the pull request returns a value) is the same shape as one observation that has both sides. The title claim "Don't raise IndexError" covers both names. When the probe already has claim C1 and that claim expects a difference, the pair is linked to C1 even if its cover patterns do not match those names.
3. The claims call is tried once more when it fails with TimeoutError. Any other claims error is still recorded on the first failure. Probe calls are unchanged.

## Why

The re-run kept the claims and wrote probes named `model-probe-c1` with the description `C1`, and observation names such as `c1_exception`. The frozen probe still had `claims: []`. The retry was asked for the claim ids and still linked nothing. The fill that attaches every known claim runs on a product check only, so this study run never filled the list. The differences then read as unclaimed.

sqlparse's title is "Don't raise IndexError ...". The probe did show that: main raised IndexError, and the pull request returned `( AS )`. It stored the raise and the value under two names, and each name is absent on the other side. The title claim only matches one observation that has the raise on main and a value on the pull request, so it covered neither name.

toolz never got as far as a probe. The claims call failed with TimeoutError, and that call was not tried again.

## Decision

- The retry that asks the model to name claim ids stays. Filling runs only on the answer that is kept, and only when that answer is still blank.
- A study run attaches a known claim only when the probe's description, id, or recorded observation names already point at that claim. It does not attach the other claims. A product check still attaches every known testable claim, as it did before.
- A claim the probe did write is not replaced and not expanded.
- The split pair is one shape only when a prefix has exactly one raise-and-absent observation and exactly one absent-and-value observation. Any other count is left as separate observations.
- The pair links to a claim id that matches its prefix only when that claim expects a difference. A claim that expects no change is not treated as proven by the pair. With no such claim, the title claim can still cover the pair.
- The claims retry is one extra call, and only for TimeoutError.

## Alternatives and tradeoffs

- Attaching every known claim on a study run would link a probe that prints `c1.*` and `c2.*` to a "same" claim it was not written for. The signals limit the fill to the names the probe already used. A probe that prints both prefixes still receives both claims.
- Leaving the two sqlparse observations unclaimed keeps the title from counting a change the probe did record. Pairing every absent value with every exception in the probe would join unrelated checks. One raise and one value under the same prefix is the only pair.
- Retrying every claims error would repeat a refusal or a bad request. Only a timeout is tried again, and only once.

## What it means for you

- A study-run probe that forgets its claim list, but is named for a claim or prints that claim's observation names, is frozen with those claim ids. The plan records `model_claims_filled`.
- A title such as "Don't raise IndexError" counts when the raise and the returned value are two sibling observations, and those two are linked to claim C1 when the probe lists C1 as a difference.
- A claims call that times out is tried once more. If the second call also times out, the record shows the same timeout error.

## Offline proof

The fixtures under `tests/fixtures/rerun_06e3e5c/` are the probe ids, descriptions, observation names, and the claims error from the re-run. They contain no machine paths. `tests/test_rerun_06e3e5c_fixes.py` checks the three fills, the split shape against the recorded sqlparse values, and one claims retry. Nothing from the pull requests is run again.
