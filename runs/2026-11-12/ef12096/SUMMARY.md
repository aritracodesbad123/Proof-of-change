# Proof-of-Change go/no-go: 2026-11-12 on ef12096

3 report(s) in this folder: 0 need attention, 1 could not be verified, 2 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **COULD NOT VERIFY**: python-attrs/attrs#1657: Add attrs.fields_equal() for class-agnostic field comparison. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 8 test(s) fail on main and pass on the PR; 192 test(s) ran on main, 192 on the PR; 0 new test(s) pass, 186 unchanged (2 of them skipped on both sides)

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| COULD NOT VERIFY | python-attrs/attrs#1657: Add attrs.fields_equal() for class-agnostic field comparison | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 8 test(s) fail on main and pass on the PR; 192 test(s) ran on main, 192 on the PR; 0 new test(s) pass, 186 unchanged (2 of them skipped on both sides) | [PDF](attrs-1657/REPORT.pdf) |
| VERIFIED | mahmoud/boltons#757: Preserve required fields in repr helpers | 2 test(s) fail on main and pass on the PR; 48 test(s) ran on main, 48 on the PR; 0 new test(s) pass, 46 unchanged; probe: 5 observation(s) ignored as noise (they change between runs of the same side); probe: 2 unchanged sub-check(s) of an input where the claim's change was seen, shown as advisory only: c2.exp_repr_optional_only (C2); c4.exp_repr_optional_only (C4); probe: claim(s) C1, C2, C3, C4 proven | [PDF](boltons-757/REPORT.pdf) |
| VERIFIED | mahmoud/boltons#763: Accept file-style seek on DummyFile | 13 test(s) ran on main, 15 on the PR; 2 new test(s) pass, 13 unchanged; probe: claim(s) C1, C2, C3, C4 proven; probe: 1 probe(s) could not run on either side | [PDF](boltons-763/REPORT.pdf) |
