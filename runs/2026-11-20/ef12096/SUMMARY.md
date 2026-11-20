# Proof-of-Change go/no-go: 2026-11-20 on ef12096

3 report(s) in this folder: 0 need attention, 2 could not be verified, 1 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **COULD NOT VERIFY**: mahmoud/boltons#815: fix(urlutils): preserve explicitly empty query parameter values. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 3 test(s) fail on main and pass on the PR; 175 test(s) ran on main, 176 on the PR; 1 new test(s) pass, 172 unchanged
- **COULD NOT VERIFY**: mahmoud/boltons#817: Accept uppercase hexadecimal prefixes in Bits. Could not verify: difference(s) no linked claim covers (model-p1 c1.upper_exc, model-p2 c2.upper_exc), so the change is not confirmed (9 test(s) fail on main and pass on the PR; 25 test(s) ran on main, 26 on the PR; 1 new test(s) pass, 16 unchanged; probe: 2 difference(s) no linked claim covers, shown as advisory only: c1.upper_exc, c2.upper_exc; probe: 7 unchanged sub-check(s) of an input where the claim's change was seen, shown as advisory only: c1.lower_len (C1); c1.lower_success (C1); c1.lower_val (C1); c2.lower_len (C2); probe: claim(s) C1, C2, C3 proven)

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| COULD NOT VERIFY | mahmoud/boltons#815: fix(urlutils): preserve explicitly empty query parameter values | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 3 test(s) fail on main and pass on the PR; 175 test(s) ran on main, 176 on the PR; 1 new test(s) pass, 172 unchanged | [PDF](boltons-815/REPORT.pdf) |
| COULD NOT VERIFY | mahmoud/boltons#817: Accept uppercase hexadecimal prefixes in Bits | Could not verify: difference(s) no linked claim covers (model-p1 c1.upper_exc, model-p2 c2.upper_exc), so the change is not confirmed (9 test(s) fail on main and pass on the PR; 25 test(s) ran on main, 26 on the PR; 1 new test(s) pass, 16 unchanged; probe: 2 difference(s) no linked claim covers, shown as advisory only: c1.upper_exc, c2.upper_exc; probe: 7 unchanged sub-check(s) of an input where the claim's change was seen, shown as advisory only: c1.lower_len (C1); c1.lower_success (C1); c1.lower_val (C1); c2.lower_len (C2); probe: claim(s) C1, C2, C3 proven) | [PDF](boltons-817/REPORT.pdf) |
| VERIFIED | mahmoud/boltons#813: Report out-of-range indices in get_path diagnostics | 2 test(s) fail on main and pass on the PR; 60 test(s) ran on main, 60 on the PR; 0 new test(s) pass, 58 unchanged; probe: claim(s) C2, C5 proven; probe: 2 probe(s) could not run on either side; probe model-probe1 is not_adequate (ran none of the 1 changed line(s) on the main side); its results do not count either way; probe model-probe4 is not_adequate (ran none of the 1 changed line(s) on the main side); its results do not count either way | [PDF](boltons-813/REPORT.pdf) |
