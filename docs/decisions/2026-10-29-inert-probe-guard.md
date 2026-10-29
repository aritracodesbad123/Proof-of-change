# A probe whose every value is empty on both sides is a broken probe, never evidence

## Problem

On the rich #4147 live check (2026-10-29, 10:31 IST) both model probes built a `Text`, called the highlighter on
it and then read the spans of the original object. The highlighter returns a new highlighted `Text` and leaves its
argument unchanged, so every observation was `[]` on main and on the PR in all 3 runs. "12 observations identical
on both sides" let the check end as verified, although the probes never saw the changed regex.

## Change

- `ops/daily_run.inert_probe_gate` (in `gate`, after the broken-probe gate): when the record is verified and every
  probe is inert or broken, with at least one inert, the verdict becomes could_not_verify with the reason
  "broken probe, every value it returned is empty on both sides". `all_inert` holds when every observation's main
  and PR value and every value of every saved run is `None`, `[]`, `{}` or `""`. `0` and `False` are values, not
  empty. The gate never raises a verdict and is idempotent. Rejudging an old record applies it too.
- `PRODUCT_PROBE_RULES` (product route probes prompt): observe the value the changed call returns, because many
  calls return a new object and leave their argument unchanged, so read the result from the return value, not
  from the input. All-empty values prove nothing. Every probe must list the claim ids it checks and start its
  observation names with them. The rule is generic on purpose: it names no rich class or call, so a later #4147
  check stays an unaided measurement.

## Offline proof (no live run, no credits)

The two frozen probes from that run were hand-fixed only on the call line (`t = h(Text(s))`) and run 3 times each
against rich base 9d8f9a37 and head 3bd56b51 (the live140 SHAs), each importing rich from its own source tree.
Outputs, the fixed probes and the replay script are in `tests/fixtures/inert_probe/`.

- Original probes: all 12 observations empty on both sides in all runs, so the new gate makes them could_not_verify.
- Fixed probes, past-boundary inputs `followed` (`<a>content</a>zz`) and `preceded` (`xx<a>content</a>yy`): main
  gives `repr.tag_*` spans in every run; the PR gives no tag spans in any run, only path/filename spans. Stable on
  each side.
- Replaying the live record with the fixed outputs through `rejudge` and `final()`:
  - no claim links (as the model wrote them): needs_attention, unmentioned differences;
  - linked to the model's own claims C1 and C3, both of which it marked `expect: differs`: verified. The
    differences count as the claimed change;
  - C3 linked as a "behaviour preserved" claim (`expect: same`, the reading of "while preserving existing
    behavior"): needs_attention with false_claim on `C3.followed`, `C3.preceded` and the other inputs.

So the fix makes the probe observe the regression. A false_claim also needs a "same" claim on those inputs, and
that depends on how the claims step reads the PR text. That part is not changed here.

## Not done, on purpose

No live run. The literal `"\\n"` in the probes' newline inputs (a backslash and n, not a newline) was left as the
model wrote it. One inert probe next to a probe with real values does not trip the gate, matching the broken-probe
gate. No guard test is weakened.

## Tests

The full-gate fixture carries the live record's coverage block (the tests ran the changed line), so
`no_evidence_gate` leaves it alone and only the inert guard demotes it; a test replaces the guard with a no-op
and checks the record then stays verified.


`tests/test_inert_probe_gate.py`: the live record's probe items (fixture) trip the gate and the full `gate` chain;
one non-empty value anywhere clears it; the gate never raises a verdict; the prompt rule wording; the offline proof
outputs (original inert, fixed: tags on main and none on the PR for the past-boundary inputs, the replay verdicts).
