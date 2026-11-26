# Proof-of-Change go/no-go: 2026-11-26 on 748f814

4 report(s) in this folder: 1 need attention, 1 could not be verified, 2 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **NEEDS ATTENTION**: mahmoud/boltons#841: Apply the configured default for empty FunctionBuilder bodies. Probe: 2 observation(s) need attention: c5.''.func_returns_none differs and no claim covers it; c5.None.func_returns_none differs and no claim covers it; probe: claim(s) C2, C6 proven; probe: 2 other observation(s) identical on both sides; tests: 8 test(s) fail on main and pass on the PR; 39 test(s) ran on main, 43 on the PR; 4 new test(s) pass, 31 unchanged
- **COULD NOT VERIFY**: python-attrs/attrs#1667: perf: optimize asdict, astuple, and fields fast paths. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 341 test(s) ran on main, 342 on the PR; 1 new test(s) pass, 341 unchanged

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| NEEDS ATTENTION | mahmoud/boltons#841: Apply the configured default for empty FunctionBuilder bodies | Probe: 2 observation(s) need attention: c5.''.func_returns_none differs and no claim covers it; c5.None.func_returns_none differs and no claim covers it; probe: claim(s) C2, C6 proven; probe: 2 other observation(s) identical on both sides; tests: 8 test(s) fail on main and pass on the PR; 39 test(s) ran on main, 43 on the PR; 4 new test(s) pass, 31 unchanged | [PDF](boltons-841/REPORT.pdf) |
| COULD NOT VERIFY | python-attrs/attrs#1667: perf: optimize asdict, astuple, and fields fast paths | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 341 test(s) ran on main, 342 on the PR; 1 new test(s) pass, 341 unchanged | [PDF](attrs-1667/REPORT.pdf) |
| VERIFIED | mahmoud/boltons#838: fix: infer table columns from mappings with mixed key types | 2 test(s) fail on main and pass on the PR; 12 test(s) ran on main, 13 on the PR; 1 new test(s) pass, 10 unchanged; probe: 1 observation(s) shown as advisory only (the probe input may not reach the changed code; the tests already prove the change): c2.comparable (C2); probe: claim(s) C2 proven | [PDF](boltons-838/REPORT.pdf) |
| VERIFIED | mahmoud/boltons#839: Reject anonymous format fields under python -O | 5 test(s) ran on main, 7 on the PR; 2 new test(s) pass, 5 unchanged; probe: claim(s) C1 proven; probe: 1 probe(s) could not run on either side | [PDF](boltons-839/REPORT.pdf) |
