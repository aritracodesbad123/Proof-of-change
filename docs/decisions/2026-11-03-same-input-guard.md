# An agreeing differs claim is not excused on an input that already changed

## What changed

A claim that says behaviour changes, and whose covered observations all agree (the same value on both sides),
is still advisory when another differs claim on the record is already proven. That is unchanged. What is new
is an input check. The input is the dotted observation name without its last part, the same split already
used when one value of a claim meets that claim.

An agreeing observation is excused only when no other claim is proven different on that same input. If
another claim differs there, the agreeing observation keeps its needs-attention flag. The change was reached
on that input, so "the claim was not shown" is the wrong reading.

The same check applies to a cross-run (a test the pull request added or edited that fails on the base and
passes on the pull request). A cross-run must not settle a differs claim whose agreeing observations sit on
an input where another claim was proven different. A differs claim whose probes never ran has no such
observation, so a cross-run may still settle it. Nothing in the rule names a repository or a pull request.

## Why

On python-barcode pull request 162, claim C3 says FNC4 is used for high characters in charsets A and B. The
probe reported `uses_fnc4` false on both sides for the inputs low160 and high255, so C3 agreed. Claims C1
and C2 were proven, and the earlier rule excused C3 for that reason alone. On those same inputs, though, C1
and C2 flipped: IllegalCharacterError on the base, accepted on the pull request. The probe had reached the
change, and C3 had failed. Excusing it left the check at could not verify. It should be needs attention.

## Decision

- The check runs where an agreeing differs observation is turned into an advisory note, and again where a
  cross-run chooses which differs claims it may settle.
- "The same input" means the same prefix from that split. An undotted name has no input that can be told
  apart, so this guard does not apply to it.
- "Proven different" means a probe observation labelled proven, whose two sides differ, that is not advisory
  and not unstable only on the pull request. A claim proven only as "the result stays the same" does not
  count. A proof on a different input does not count.
- One dirty observation is enough. The agreeing claim keeps needs attention, and a cross-run does not settle
  that claim. An observation of the same claim on a different, clean input can still be advisory.
- A true contradiction, a differs claim that is only partly shown, and a record with nothing proven are
  unchanged.

## Alternatives and tradeoffs

- Excusing every agreeing differs claim once anything on the record is proven is what hid this miss. The
  proof has to be on a different input.
- Refusing to excuse any agreeing claim whenever another claim is proven anywhere would bring back the
  loguru, toolz and attrs cases, where the agreeing observations are on inputs the proven claims did not use.
- Letting a cross-run settle the claim anyway would verify the same miss as soon as the pull request has one
  new or changed test that fails on the base and passes on the pull request.

## What it means for you

A check no longer treats "does not differ, although the claim says it does" as advisory when that
observation's input is one where another claim was shown to change. That observation needs attention, and a
passing cross-run does not clear it. An agreeing claim on inputs where nothing else was proven different is
unchanged, including one a cross-run settles because its probes never ran.

## Offline proof

`tests/fixtures/same_input_guard/barcode-162.json` is modelled on that pull request: C1 and C2 differ on
low160 and high255, and C3 agrees on those same inputs. `tests/test_same_input_guard.py` re-judges it.
Needs attention, both with and without a passing cross-run. Nothing from the pull request is run again.

`scripts/rejudge_same_input.py` prints the verdict before and after this guard. Before is the previous
rule. Six readings that the previous rules had settled stay settled:

- loguru pull request 1536: verified
- toolz pull request 654: verified
- attrs pull request 1647, the linking test: verified
- attrs pull request 1647, claim linking with the stored comparison: could not verify (behaviour claims hold
  it there; C4 stays advisory, because its inputs are not the inputs C1 and C3 differ on)
- the narrow cross-run fixture where the probes agreed: verified
- the narrow cross-run fixture whose differs claim never ran: verified

None flip back. The modelled barcode fixture is the miss: verified before, needs attention after, with and
without the cross-run. Judging the attrs file without re-linking claim covers also stays could not verify;
that path does not apply this rule.

84 stored `record.json` files were considered. 44 of them have probe results and were re-judged. No verdict
changes. The 2026-11-03 held-out set (ce 556, 557 and 559, altair 4189 and 4203, requests 7068 and 7413,
rich 4157, isort 2778, 2748 and 2674, click 3902, jsonschema 1561 and 1515, invoke 1097, 1098 and 1099,
pingouin 554) has no matching record in the repo.
