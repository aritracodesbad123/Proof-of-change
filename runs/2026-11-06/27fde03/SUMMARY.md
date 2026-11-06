# Proof-of-Change check: 2026-11-06-219-27fde03-v2

Generated 2026-11-06 14:46 IST. 1 report(s): 1 need attention, 0 could not be verified, 0 verified. Items that need a decision are listed first.

## Needs attention first

- **NEEDS ATTENTION / Reject** (High confidence): Delgan/loguru#1515: Evaluate every rotation condition so a skipped one cannot fire spuriously, tested against its own tests. Probe: 1 observation(s) need attention: c2.ret_msg2 differs although the claim says it does not (C2); probe: 5 unchanged sub-check(s) of an input where the claim's change was seen, shown as advisory only: c1.cond0_limit_after_msg1 (C1); c1.cond0_limit_after_msg2 (C1); c1.cond1_initialized_after_msg1 (C1); c1.cond1_initialized_after_msg2 (C1); probe: 2 observation(s) shown as advisory only (claim not shown on these inputs; a related change was proven): c3.cond1_limit_after_msg1_in_past (C3); c3.cond1_limit_after_msg2_in_past (C3); probe: claim(s) C1, C2, C4 proven; tests: 1 test(s) fail on main and pass on the PR; 148 test(s) ran on main, 148 on the PR; 0 new test(s) pass, 150 unchanged (3 of them skipped on both sides). [Open report](loguru-1515/REPORT.html) ([PDF](loguru-1515/REPORT.pdf))

## All reports

| Verdict | Action | Confidence | Subject | Tested against | Why | Evals | Report |
|---|---|---|---|---|---|---|---|
| 🟠 **NEEDS ATTENTION** | 🔴 **Reject** | High | Delgan/loguru#1515: Evaluate every rotation condition so a skipped one cannot fire spuriously | its own tests | probe: 1 observation(s) need attention: c2.ret_msg2 differs although the claim says it does not (C2); probe: 5 unchanged sub-check(s) of an input where the claim's change was seen, shown as advisory only: c1.cond0_limit_after_msg1 (C1); c1.cond0_limit_after_msg2 (C1); c1.cond1_initialized_after_msg1 (C1); c1.cond1_initialized_after_msg2 (C1); probe: 2 observation(s) shown as advisory only (claim not shown on these inputs; a related change was proven): c3.cond1_limit_after_msg1_in_past (C3); c3.cond1_limit_after_msg2_in_past (C3); probe: claim(s) C1, C2, C4 proven; tests: 1 test(s) fail on main and pass on the PR; 148 test(s) ran on main, 148 on the PR; 0 new test(s) pass, 150 unchanged (3 of them skipped on both sides) | 🟢 **APPROVE** | [HTML](loguru-1515/REPORT.html) · [PDF](loguru-1515/REPORT.pdf) · [MD](loguru-1515/REPORT.md) |

## Verdict meanings

| Verdict | Meaning |
|---|---|
| 🟠 **NEEDS ATTENTION** | The run is trustworthy and found a problem: breaks, import failures, or a false claim. |
| ⚪ **COULD NOT VERIFY** | The run failed its own trust checks or the evals (no conclusion; re-run after fixing), or, for PR runs, the tests never exercised the changed code (review by hand). |
| 🟢 **VERIFIED** | The run is trustworthy and found no behavior change. |
