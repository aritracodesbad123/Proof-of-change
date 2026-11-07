# Proof-of-Change daily summary: 2026-11-07

Generated 2026-11-07 11:36 IST. 3 report(s): 0 need attention, 3 could not be verified, 0 verified. Items that need a decision are listed first.

## Needs attention first

- **COULD NOT VERIFY / Re-run** (Low confidence): python-jsonschema/jsonschema#1534: Support Draft 2020-12 relative JSON Pointer index manipulation, tested against its own tests. Unverified behaviour claim: "Keep the Draft 7 and Draft 2019-09 checker behavior unchanged."; needs a probe (1 test(s) fail on main and pass on the PR; 7843 test(s) ran on main, 7845 on the PR; 2 new test(s) pass, 8074 unchanged (232 of them skipped on both sides)). [Open report](jsonschema-1534/REPORT.html) ([PDF](jsonschema-1534/REPORT.pdf))
- **COULD NOT VERIFY / Re-run** (Low confidence): prettytable/prettytable#539: Preserve numeric values when importing CSV, tested against its own tests. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 2 test(s) fail on main and pass on the PR; 282 test(s) ran on main, 282 on the PR; 0 new test(s) pass, 280 unchanged. [Open report](prettytable-539/REPORT.html) ([PDF](prettytable-539/REPORT.pdf))
- **COULD NOT VERIFY / Re-run** (Low confidence): urllib3/urllib3#5354: Clamp Retry-After values that are too long for int() instead of raising ValueError, tested against its own tests. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 2 test(s) fail on main and pass on the PR; 77 test(s) ran on main, 79 on the PR; 2 new test(s) pass, 75 unchanged. [Open report](urllib3-5354/REPORT.html) ([PDF](urllib3-5354/REPORT.pdf))

## All reports

| Verdict | Action | Confidence | Subject | Tested against | Why | Evals | Report |
|---|---|---|---|---|---|---|---|
| ⚪ **COULD NOT VERIFY** | ⚪ **Re-run** | Low | python-jsonschema/jsonschema#1534: Support Draft 2020-12 relative JSON Pointer index manipulation | its own tests | unverified behaviour claim: "Keep the Draft 7 and Draft 2019-09 checker behavior unchanged."; needs a probe (1 test(s) fail on main and pass on the PR; 7843 test(s) ran on main, 7845 on the PR; 2 new test(s) pass, 8074 unchanged (232 of them skipped on both sides)) | 🟢 **APPROVE** | [HTML](jsonschema-1534/REPORT.html) · [PDF](jsonschema-1534/REPORT.pdf) · [MD](jsonschema-1534/REPORT.md) |
| ⚪ **COULD NOT VERIFY** | ⚪ **Re-run** | Low | prettytable/prettytable#539: Preserve numeric values when importing CSV | its own tests | not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 2 test(s) fail on main and pass on the PR; 282 test(s) ran on main, 282 on the PR; 0 new test(s) pass, 280 unchanged | 🟢 **APPROVE** | [HTML](prettytable-539/REPORT.html) · [PDF](prettytable-539/REPORT.pdf) · [MD](prettytable-539/REPORT.md) |
| ⚪ **COULD NOT VERIFY** | ⚪ **Re-run** | Low | urllib3/urllib3#5354: Clamp Retry-After values that are too long for int() instead of raising ValueError | its own tests | not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 2 test(s) fail on main and pass on the PR; 77 test(s) ran on main, 79 on the PR; 2 new test(s) pass, 75 unchanged | 🟢 **APPROVE** | [HTML](urllib3-5354/REPORT.html) · [PDF](urllib3-5354/REPORT.pdf) · [MD](urllib3-5354/REPORT.md) |

## Verdict meanings

| Verdict | Meaning |
|---|---|
| 🟠 **NEEDS ATTENTION** | The run is trustworthy and found a problem: breaks, import failures, or a false claim. |
| ⚪ **COULD NOT VERIFY** | The run failed its own trust checks or the evals (no conclusion; re-run after fixing), or, for PR runs, the tests never exercised the changed code (review by hand). |
| 🟢 **VERIFIED** | The run is trustworthy and found no behavior change. |
