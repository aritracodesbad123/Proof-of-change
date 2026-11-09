# Proof-of-Change go/no-go: 2026-11-09 on ef12096

2 report(s) in this folder: 1 need attention, 1 could not be verified, 0 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **NEEDS ATTENTION**: mahmoud/boltons#744: Limit complement_int_list traversal to the requested window. Probe: 2 observation(s) need attention: c1.output differs although the claim says it does not (C1); c3.output differs although the claim says it does not (C3); probe: 1 observation(s) ignored as noise (they change between runs of the same side); probe model-probe1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; tests: 1 test(s) fail on main and pass on the PR; 47 test(s) ran on main, 47 on the PR; 0 new test(s) pass, 46 unchanged
- **COULD NOT VERIFY**: mahmoud/boltons#743: Keep inferred fields in headerless table factories. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 4 test(s) fail on main and pass on the PR; 14 test(s) ran on main, 17 on the PR; 3 new test(s) pass, 10 unchanged

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| NEEDS ATTENTION | mahmoud/boltons#744: Limit complement_int_list traversal to the requested window | Probe: 2 observation(s) need attention: c1.output differs although the claim says it does not (C1); c3.output differs although the claim says it does not (C3); probe: 1 observation(s) ignored as noise (they change between runs of the same side); probe model-probe1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; tests: 1 test(s) fail on main and pass on the PR; 47 test(s) ran on main, 47 on the PR; 0 new test(s) pass, 46 unchanged | [PDF](boltons-744/REPORT.pdf) |
| COULD NOT VERIFY | mahmoud/boltons#743: Keep inferred fields in headerless table factories | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 4 test(s) fail on main and pass on the PR; 14 test(s) ran on main, 17 on the PR; 3 new test(s) pass, 10 unchanged | [PDF](boltons-743/REPORT.pdf) |
