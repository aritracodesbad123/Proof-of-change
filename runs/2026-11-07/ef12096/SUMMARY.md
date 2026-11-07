# Proof-of-Change go/no-go: 2026-11-07 on ef12096

2 report(s) in this folder: 0 need attention, 2 could not be verified, 0 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **COULD NOT VERIFY**: python-jsonschema/jsonschema#1534: Support Draft 2020-12 relative JSON Pointer index manipulation. Unverified behaviour claim: "Keep the Draft 7 and Draft 2019-09 checker behavior unchanged."; needs a probe (1 test(s) fail on main and pass on the PR; 7843 test(s) ran on main, 7845 on the PR; 2 new test(s) pass, 8074 unchanged (232 of them skipped on both sides))
- **COULD NOT VERIFY**: prettytable/prettytable#539: Preserve numeric values when importing CSV. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 2 test(s) fail on main and pass on the PR; 282 test(s) ran on main, 282 on the PR; 0 new test(s) pass, 280 unchanged

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| COULD NOT VERIFY | python-jsonschema/jsonschema#1534: Support Draft 2020-12 relative JSON Pointer index manipulation | Unverified behaviour claim: "Keep the Draft 7 and Draft 2019-09 checker behavior unchanged."; needs a probe (1 test(s) fail on main and pass on the PR; 7843 test(s) ran on main, 7845 on the PR; 2 new test(s) pass, 8074 unchanged (232 of them skipped on both sides)) | [PDF](jsonschema-1534/REPORT.pdf) |
| COULD NOT VERIFY | prettytable/prettytable#539: Preserve numeric values when importing CSV | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 2 test(s) fail on main and pass on the PR; 282 test(s) ran on main, 282 on the PR; 0 new test(s) pass, 280 unchanged | [PDF](prettytable-539/REPORT.pdf) |
