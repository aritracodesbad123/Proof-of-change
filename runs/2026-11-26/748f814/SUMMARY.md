# Proof-of-Change go/no-go: 2026-11-26 on 748f814

2 report(s) in this folder: 0 need attention, 1 could not be verified, 1 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **COULD NOT VERIFY**: python-attrs/attrs#1667: perf: optimize asdict, astuple, and fields fast paths. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 341 test(s) ran on main, 342 on the PR; 1 new test(s) pass, 341 unchanged

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| COULD NOT VERIFY | python-attrs/attrs#1667: perf: optimize asdict, astuple, and fields fast paths | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 341 test(s) ran on main, 342 on the PR; 1 new test(s) pass, 341 unchanged | [PDF](attrs-1667/REPORT.pdf) |
| VERIFIED | mahmoud/boltons#838: fix: infer table columns from mappings with mixed key types | 2 test(s) fail on main and pass on the PR; 12 test(s) ran on main, 13 on the PR; 1 new test(s) pass, 10 unchanged; probe: 1 observation(s) shown as advisory only (the probe input may not reach the changed code; the tests already prove the change): c2.comparable (C2); probe: claim(s) C2 proven | [PDF](boltons-838/REPORT.pdf) |
