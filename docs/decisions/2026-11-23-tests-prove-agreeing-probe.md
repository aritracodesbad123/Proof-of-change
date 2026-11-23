# An agreeing probe is advisory when the tests already prove the change

## What changed

When a probe sees the same value on both sides for a claim that says the behaviour differs, and the tests
already prove that change, the probe result is an advisory note. It does not raise needs attention.

The tests prove the change only when all three of these hold: a test in a test file the pull request edits
fails on the base and passes on the pull request, every changed line that coverage counted did run, and
nothing regressed. A test id shared with the base is not that proof. The note says the probe input may not
reach the changed code.

The same result still needs attention when that proof is missing, and when another claim was already proven
different on that same input. A result that differs is unchanged. The note does not verify the pull request.
If removing it would be the only step from needs attention to verified, the verdict stays could not verify.
The other gates still decide.

The per-PR report and the summary show the note. In the probes table the row is grey and says the probe
input may not reach the changed code. The summary's why line carries the same sentence.

## Why

isort pull request 2781 printed a flat observations object. After that object is read, `c8.parts_necessary`
and `c9.number_that_change` agree on both sides while their claims say they differ. That became needs
attention. The new regression test fails on the base and passes on the pull request, coverage ran every
changed line, and nothing regressed. The probe input did not reach the change. The same shape is sqlparse
pull request 934, claims C3 and C5: both sides returned the same value because the probe never reached the
change the tests already show.

## Decision

Treat that agreeing result as advisory, and name it in the report. Do not treat it as proof, and do not let
it be the step that verifies a pull request. Leave a real difference, and an agreeing result with no test
proof, as needs attention.

## Alternatives and tradeoffs

Settling the claim as proven, the way a cross-run already can, would have marked isort 2781 verified from
this note alone. The tests there do not finish cleanly (a test module fails to load on both sides), so the
note stays advisory and the verdict stays could not verify.

Ignoring the test proof and keeping needs attention would keep the false alarm the reader was asked to remove.

## What it means for you

A probe that agrees with itself on an input the tests have already shown is a change is listed as a note,
not as needs attention. A probe that agrees, with no such tests, still needs attention. A difference the
probe actually saw still needs attention.

## Replay of saved records

The runs branch was read at `94972dc8a2216de13f05416c337f14b97a65d27a` and judged with `f20a12d` and with
this change. Saved records were not rewritten. No model was called. Where a record stored a rejected flat
JSON object under `probe.error`, that object was parsed again. No record kept a separate stdout.

258 `record.json` files. 170 judged, 165 unchanged, 5 changed, 0 errors. 88 had no probe items.

Nothing moved to verified. Held-out mahmoud/boltons #751 and #758 stay verified. #752 stays could not verify.
#803 has no probe items, so it was not judged; its stored verdict stays could not verify.

PyCQA/isort #2781 (`runs/2026-11-05/985a7ea/isort-2781/record.json`) stays could not verify. It is not needs
attention. `c8.parts_necessary` and `c9.number_that_change` are the advisory note. A test module fails to
load on both sides, so the tests do not verify the pull request either.

The five changes, each needs attention to could not verify:

- andialbrecht/sqlparse #884. The agreeing probe results are the advisory note. That note does not verify
  the pull request.
- pyinvoke/invoke #1099, two records. Same note. No model probe ran a changed line, and the note does not
  verify the pull request.
- urllib3/urllib3 #5352. The agreeing probe no longer raises attention. What remains is the recorded
  environment failure: the tests failed to bind a local socket on the base as well.
- andialbrecht/sqlparse #934. C3 and C5 are the advisory note (the probe input did not reach the change).
  The sentence about the cached `normalized` value is the old behaviour, not a broken promise, and the
  behaviour-claim gate leaves the record could not verify.

36 records have a probe-output parse error. 4 of those are recovered from the rejected JSON object. 6 would
trigger the one output retry. The retry was not run. Given only what the saved records contain, each of
those six stays could not verify: mahmoud/boltons #746, python-attrs/attrs #1654,
lincolnloop/python-qrcode #425, pytoolz/toolz #664, PyCQA/isort #2664, and mahmoud/boltons #824.
