# Proof-of-Change go/no-go: 2026-11-17 on ef12096

2 report(s) in this folder: 1 need attention, 1 could not be verified, 0 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **NEEDS ATTENTION**: python-attrs/attrs#1659: Fix initializer metadata shadowing by valid parameter names. Probe: 4 observation(s) need attention: c5.construction_exception_message does not differ although the claim says it does (C5); c5.construction_exception_type does not differ although the claim says it does (C5); c5.construction_success does not differ although the claim says it does (C5); c5.field_value does not differ although the claim says it does (C5); probe: claim(s) C8 proven; probe: 1 other observation(s) identical on both sides; tests: 1401 test(s) ran on main, 1493 on the PR; 92 new test(s) pass, 1412 unchanged (11 of them skipped on both sides)
- **COULD NOT VERIFY**: mahmoud/boltons#197: Add strutils.assemble. Install failed (1); see setup-main.log

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| NEEDS ATTENTION | python-attrs/attrs#1659: Fix initializer metadata shadowing by valid parameter names | Probe: 4 observation(s) need attention: c5.construction_exception_message does not differ although the claim says it does (C5); c5.construction_exception_type does not differ although the claim says it does (C5); c5.construction_success does not differ although the claim says it does (C5); c5.field_value does not differ although the claim says it does (C5); probe: claim(s) C8 proven; probe: 1 other observation(s) identical on both sides; tests: 1401 test(s) ran on main, 1493 on the PR; 92 new test(s) pass, 1412 unchanged (11 of them skipped on both sides) | [PDF](attrs-1659/REPORT.pdf) |
| COULD NOT VERIFY | mahmoud/boltons#197: Add strutils.assemble | Install failed (1); see setup-main.log | [PDF](boltons-197/REPORT.pdf) |
