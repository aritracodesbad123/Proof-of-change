# Proof-of-Change go/no-go: 2026-11-16 on ef12096

2 report(s) in this folder: 1 need attention, 1 could not be verified, 0 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **NEEDS ATTENTION**: mahmoud/boltons#792: fix: preserve UTF-16/32 reverse line boundaries. Probe: 6 observation(s) need attention: c2.unicode_decode_error differs although the claim says it does not (C2); c4.explicit.line0 differs and no claim covers it; c4.explicit.line1 differs and no claim covers it; c4.generic.line0 differs and no claim covers it; probe: claim(s) C1, C3 proven; probe: 1 other observation(s) identical on both sides; tests: 112 test(s) fail on main and pass on the PR; 124 test(s) ran on main, 421 on the PR; 297 new test(s) pass, 12 unchanged
- **COULD NOT VERIFY**: mahmoud/boltons#794: Preserve hidden basenames in augpath multidot mode. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 4 test(s) fail on main and pass on the PR; 9 test(s) ran on main, 9 on the PR; 0 new test(s) pass, 5 unchanged

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| NEEDS ATTENTION | mahmoud/boltons#792: fix: preserve UTF-16/32 reverse line boundaries | Probe: 6 observation(s) need attention: c2.unicode_decode_error differs although the claim says it does not (C2); c4.explicit.line0 differs and no claim covers it; c4.explicit.line1 differs and no claim covers it; c4.generic.line0 differs and no claim covers it; probe: claim(s) C1, C3 proven; probe: 1 other observation(s) identical on both sides; tests: 112 test(s) fail on main and pass on the PR; 124 test(s) ran on main, 421 on the PR; 297 new test(s) pass, 12 unchanged | [PDF](boltons-792/REPORT.pdf) |
| COULD NOT VERIFY | mahmoud/boltons#794: Preserve hidden basenames in augpath multidot mode | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 4 test(s) fail on main and pass on the PR; 9 test(s) ran on main, 9 on the PR; 0 new test(s) pass, 5 unchanged | [PDF](boltons-794/REPORT.pdf) |
