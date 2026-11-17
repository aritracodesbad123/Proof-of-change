# Proof-of-Change go/no-go: 2026-11-17 on ef12096

6 report(s) in this folder: 1 need attention, 4 could not be verified, 1 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **NEEDS ATTENTION**: python-attrs/attrs#1659: Fix initializer metadata shadowing by valid parameter names. Probe: 4 observation(s) need attention: c5.construction_exception_message does not differ although the claim says it does (C5); c5.construction_exception_type does not differ although the claim says it does (C5); c5.construction_success does not differ although the claim says it does (C5); c5.field_value does not differ although the claim says it does (C5); probe: claim(s) C8 proven; probe: 1 other observation(s) identical on both sides; tests: 1401 test(s) ran on main, 1493 on the PR; 92 new test(s) pass, 1412 unchanged (11 of them skipped on both sides)
- **COULD NOT VERIFY**: mahmoud/boltons#197: Add strutils.assemble. Install failed (1); see setup-main.log
- **COULD NOT VERIFY**: mahmoud/boltons#799: Validate anonymous format arguments under Python optimization. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 5 test(s) ran on main, 6 on the PR; 1 new test(s) pass, 5 unchanged; probe model-p1 is not_adequate (ran none of the 4 changed line(s) on the main side); its results do not count either way
- **COULD NOT VERIFY**: pyinvoke/invoke#278: A bunch of work for refactoring Program re #276. No tests could be mapped to the touched files
- **COULD NOT VERIFY**: Delgan/loguru#1545: Fix file sink stuck on closed file after close error during rotation. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 152 test(s) ran on main, 152 on the PR; 0 new test(s) pass, 154 unchanged (3 of them skipped on both sides)

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| NEEDS ATTENTION | python-attrs/attrs#1659: Fix initializer metadata shadowing by valid parameter names | Probe: 4 observation(s) need attention: c5.construction_exception_message does not differ although the claim says it does (C5); c5.construction_exception_type does not differ although the claim says it does (C5); c5.construction_success does not differ although the claim says it does (C5); c5.field_value does not differ although the claim says it does (C5); probe: claim(s) C8 proven; probe: 1 other observation(s) identical on both sides; tests: 1401 test(s) ran on main, 1493 on the PR; 92 new test(s) pass, 1412 unchanged (11 of them skipped on both sides) | [PDF](attrs-1659/REPORT.pdf) |
| COULD NOT VERIFY | mahmoud/boltons#197: Add strutils.assemble | Install failed (1); see setup-main.log | [PDF](boltons-197/REPORT.pdf) |
| COULD NOT VERIFY | mahmoud/boltons#799: Validate anonymous format arguments under Python optimization | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 5 test(s) ran on main, 6 on the PR; 1 new test(s) pass, 5 unchanged; probe model-p1 is not_adequate (ran none of the 4 changed line(s) on the main side); its results do not count either way | [PDF](boltons-799/REPORT.pdf) |
| COULD NOT VERIFY | pyinvoke/invoke#278: A bunch of work for refactoring Program re #276 | No tests could be mapped to the touched files | [PDF](invoke-278/REPORT.pdf) |
| COULD NOT VERIFY | Delgan/loguru#1545: Fix file sink stuck on closed file after close error during rotation | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 152 test(s) ran on main, 152 on the PR; 0 new test(s) pass, 154 unchanged (3 of them skipped on both sides) | [PDF](loguru-1545/REPORT.pdf) |
| VERIFIED | mahmoud/boltons#797: dictutils: apply update_extend's keyword arguments | 2 test(s) fail on main and pass on the PR; 100 test(s) ran on main, 100 on the PR; 0 new test(s) pass, 98 unchanged; probe: claim(s) C1, C2 proven | [PDF](boltons-797/REPORT.pdf) |
