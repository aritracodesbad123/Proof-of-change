# A bare observations object is read, and an unreadable probe is sent back once

## What changed

A probe's printed output is read in two shapes. The usual one is unchanged: the last line is a JSON object
`{"observations": {"name": value, ...}}`. A bare object is now also read, but only when the shape is unambiguous.
Every key must be an observation id (a claim-linked name such as `c1.shape_access` or `c2_rows`, or a dotted name),
or every key must be a name the probe was asked to cover. The object must not use a wrapper or status key
(`observations`, `crash`, `timeout`, `exit_code`, `contract`, `error`, `stderr`, `traceback`, `exception`,
`message`). A mix of those keys is rejected as a whole. Nothing is filled in, nothing is taken from an earlier
line, and nothing is taken from stderr or a traceback.

If the output still cannot be read as observations on both sides, and the probe exited 0, the probe is sent back
to the model once. The request includes the exact parse error and the output contract. The rejected probe file
is kept, and the raw stdout is kept beside it under `model-probes/`. The new probe is run on both sides with the
same timeout. If that output is still wrong, the run is an error, not a set of observations. A probe gets this
call or the existing crash rewrite, never both, and never a second call. The same rule that stops a rewrite from
raising a verdict still applies.

## Why

prettytable pull request 558 printed a flat JSON object whose keys were the observation ids. The reader required
the `observations` wrapper, so both sides were stored as an error and the record was could not verify. The values
were in the output. They were not read.

Some other probes print a Python dict, or print nothing that is JSON. Those still fail this reader. They get one
chance to print the contract, and the rejected file stays so the failure can be audited.

## Decision

Accept a bare object only when every key is an observation id, or every key matches a cover the probe was asked
for. One key that does not match rejects the whole object. A single plain word such as `{"no": "observations"}`
stays an error. A wrapped object is still the normal form, and a non-zero exit or a timeout is still a crash,
not this retry.

The retry does not run in a replay. It would call the model. The replay only counts how many saved records would
have triggered it.

Re-reading a saved record does not by itself turn needs attention into verified. The tests, the other claims, and
the existing gates still decide. A real disagreement still needs attention.

## Alternatives and tradeoffs

Accepting every JSON object that lacks a wrapper key would have treated `{"no": "observations"}` as an
observation and could hide a real difference behind two identical junk values. That was rejected.

Merging a valid key out of a mixed object was rejected for the same reason. The object is kept or dropped whole.

Sending the probe back more than once would spend another model call and another pair of runs. One call is the
budget the crash rewrite already had. This path uses that one call when the failure is unread output on both
sides.

## What it means for you

A probe that prints `{"c1.name": value, ...}` is scored. A probe that prints garbage is still an error. If both
sides printed something that cannot be read, the check asks once for a last line in the usual wrapper and keeps
the rejected file. A saved record is not rewritten.

## Replay of saved records

The runs branch was read at `94972dc8a2216de13f05416c337f14b97a65d27a`. It holds 258 `record.json` files
(4 November 2026 through 23 November 2026). Each file was judged with the code at `f20a12d` and with this
change. No model was called, and no saved file was rewritten.

170 files had a verdict and probe items and were judged. 88 had no probe items, so there was nothing to judge.
169 judged files were unchanged. 1 changed. 0 errored.

No saved record kept a separate copy of the probe's stdout. 36 records have a probe-output parse error. 4 of
those stored the rejected JSON object itself under `probe.error` (the object the old reader had already parsed
and then refused). The new reader recovers those 4. The other 32 have no stdout left to read, so they stay
errors. 6 records would have triggered the one output retry (both sides still unreadable after this reader,
exit 0). The retry was not run.

The one change is PyCQA/isort #2781 at `runs/2026-11-05/985a7ea/isort-2781/record.json`, could not verify to
needs attention. The bare object was recovered. `c8.parts_necessary` and `c9.number_that_change` agree on both
sides, and their claims say they differ. The existing gates flag that. It is not a verified result.

The other three recovered records stay could not verify. prettytable #558
(`runs/2026-11-23/57cf537/prettytable-558/record.json`) is one of them. The observations are read, and they
differ where the claims said they differ, but the saved coverage was cleared when the output was rejected. The
gate still requires a probe that ran a changed line, so the verdict does not move. mahmoud/boltons #731 and
pyinvoke/invoke #1097 (`runs/2026-11-06/4050401/invoke-1097/record.json`) also stay could not verify.

The six records that would be sent back once, and were not, all stay could not verify: mahmoud/boltons #746,
python-attrs/attrs #1654, lincolnloop/python-qrcode #425, pytoolz/toolz #664, PyCQA/isort #2664, and
mahmoud/boltons #824.

No needs-attention verdict became verified. No verified verdict became could not verify.

Held-out records did not move. mahmoud/boltons #751 and #758 stay verified. #752 stays could not verify. #803
has no probe items, so it was not judged; its stored verdict stays could not verify.
