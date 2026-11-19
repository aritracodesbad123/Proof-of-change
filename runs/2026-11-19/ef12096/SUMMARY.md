# Proof-of-Change go/no-go: 2026-11-19 on ef12096

3 report(s) in this folder: 0 need attention, 1 could not be verified, 2 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **COULD NOT VERIFY**: mahmoud/boltons#809: Fix SpooledStringIO.read(None). Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 97 test(s) ran on main, 97 on the PR; 0 new test(s) pass, 96 unchanged

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| COULD NOT VERIFY | mahmoud/boltons#809: Fix SpooledStringIO.read(None) | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 97 test(s) ran on main, 97 on the PR; 0 new test(s) pass, 96 unchanged | [PDF](boltons-809/REPORT.pdf) |
| VERIFIED | PyCQA/isort#2797: fix: preserve configured lines_between_types with force_alphabetical_sort (#1972) | 2 test(s) fail on main and pass on the PR; 356 test(s) ran on main, 356 on the PR; 0 new test(s) pass, 352 unchanged (6 of them skipped on both sides); 8 test failure(s) pre-existing and identical on both sides; probe: claim(s) C2 proven | [PDF](isort-2797/REPORT.pdf) |
| VERIFIED | python-jsonschema/jsonschema#1515: Fix multipleOf crashing on Decimal instances and large integers | 1 test(s) fail on main and pass on the PR; 304 test(s) ran on main, 304 on the PR; 0 new test(s) pass, 303 unchanged; probe: 2 unchanged sub-check(s) of an input where the claim's change was seen, shown as advisory only: c1.errors_len (C1); c2.errors_len (C2); probe: claim(s) C1, C2 proven | [PDF](jsonschema-1515/REPORT.pdf) |
