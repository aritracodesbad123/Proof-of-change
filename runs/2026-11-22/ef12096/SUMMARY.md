# Proof-of-Change go/no-go: 2026-11-22 on ef12096

4 report(s) in this folder: 0 need attention, 3 could not be verified, 1 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **COULD NOT VERIFY**: mahmoud/boltons#821: fix parse_timedelta dropping units in compact strings like 1h30m. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 18 test(s) ran on main, 18 on the PR; 0 new test(s) pass, 17 unchanged
- **COULD NOT VERIFY**: mahmoud/boltons#822: fix SpooledStringIO.read(None) raising TypeError. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 97 test(s) ran on main, 97 on the PR; 0 new test(s) pass, 96 unchanged
- **COULD NOT VERIFY**: mahmoud/boltons#824: Keep FunctionBuilder custom attributes independent. Could not verify: claim(s) C1 expect a difference but no observation matches (2 test(s) fail on main and pass on the PR; 25 test(s) ran on main, 25 on the PR; 0 new test(s) pass, 23 unchanged; probe model-probe1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count)

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| COULD NOT VERIFY | mahmoud/boltons#821: fix parse_timedelta dropping units in compact strings like 1h30m | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 18 test(s) ran on main, 18 on the PR; 0 new test(s) pass, 17 unchanged | [PDF](boltons-821/REPORT.pdf) |
| COULD NOT VERIFY | mahmoud/boltons#822: fix SpooledStringIO.read(None) raising TypeError | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 97 test(s) ran on main, 97 on the PR; 0 new test(s) pass, 96 unchanged | [PDF](boltons-822/REPORT.pdf) |
| COULD NOT VERIFY | mahmoud/boltons#824: Keep FunctionBuilder custom attributes independent | Could not verify: claim(s) C1 expect a difference but no observation matches (2 test(s) fail on main and pass on the PR; 25 test(s) ran on main, 25 on the PR; 0 new test(s) pass, 23 unchanged; probe model-probe1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count) | [PDF](boltons-824/REPORT.pdf) |
| VERIFIED | encode/httpx#3856: Raise ProtocolError on malformed Digest auth challenges | 6 test(s) fail on main and pass on the PR; 93 test(s) ran on main, 93 on the PR; 0 new test(s) pass, 88 unchanged (1 of them skipped on both sides); probe: claim(s) C1, C2 proven | [PDF](httpx-3856/REPORT.pdf) |
