# Proof-of-Change go/no-go: 2026-11-22 on ef12096

2 report(s) in this folder: 0 need attention, 2 could not be verified, 0 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **COULD NOT VERIFY**: mahmoud/boltons#821: fix parse_timedelta dropping units in compact strings like 1h30m. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 18 test(s) ran on main, 18 on the PR; 0 new test(s) pass, 17 unchanged
- **COULD NOT VERIFY**: mahmoud/boltons#822: fix SpooledStringIO.read(None) raising TypeError. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 97 test(s) ran on main, 97 on the PR; 0 new test(s) pass, 96 unchanged

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| COULD NOT VERIFY | mahmoud/boltons#821: fix parse_timedelta dropping units in compact strings like 1h30m | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 18 test(s) ran on main, 18 on the PR; 0 new test(s) pass, 17 unchanged | [PDF](boltons-821/REPORT.pdf) |
| COULD NOT VERIFY | mahmoud/boltons#822: fix SpooledStringIO.read(None) raising TypeError | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 97 test(s) ran on main, 97 on the PR; 0 new test(s) pass, 96 unchanged | [PDF](boltons-822/REPORT.pdf) |
