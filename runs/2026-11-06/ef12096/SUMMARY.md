# Proof-of-Change check: 2026-11-06-220223-invoke-ef120966

Generated 2026-11-06 17:30 IST. 1 report(s): 0 need attention, 1 could not be verified, 0 verified. Items that need a decision are listed first.

## Needs attention first

- **COULD NOT VERIFY / Re-run** (Low confidence): pyinvoke/invoke#1097: Use command-line names in missing-argument errors, tested against its own tests. Could not verify: claim(s) C1, C2 expect a difference but no observation matches (2 test(s) fail on main and pass on the PR; 137 test(s) ran on main, 137 on the PR; 0 new test(s) pass, 136 unchanged (1 of them skipped on both sides); probe model-probe1-rewrite is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count). [Open report](invoke-1097/REPORT.html) ([PDF](invoke-1097/REPORT.pdf))

## All reports

| Verdict | Action | Confidence | Subject | Tested against | Why | Evals | Report |
|---|---|---|---|---|---|---|---|
| ⚪ **COULD NOT VERIFY** | ⚪ **Re-run** | Low | pyinvoke/invoke#1097: Use command-line names in missing-argument errors | its own tests | could not verify: claim(s) C1, C2 expect a difference but no observation matches (2 test(s) fail on main and pass on the PR; 137 test(s) ran on main, 137 on the PR; 0 new test(s) pass, 136 unchanged (1 of them skipped on both sides); probe model-probe1-rewrite is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count) | 🟢 **APPROVE** | [HTML](invoke-1097/REPORT.html) · [PDF](invoke-1097/REPORT.pdf) · [MD](invoke-1097/REPORT.md) |

## Verdict meanings

| Verdict | Meaning |
|---|---|
| 🟠 **NEEDS ATTENTION** | The run is trustworthy and found a problem: breaks, import failures, or a false claim. |
| ⚪ **COULD NOT VERIFY** | The run failed its own trust checks or the evals (no conclusion; re-run after fixing), or, for PR runs, the tests never exercised the changed code (review by hand). |
| 🟢 **VERIFIED** | The run is trustworthy and found no behavior change. |
