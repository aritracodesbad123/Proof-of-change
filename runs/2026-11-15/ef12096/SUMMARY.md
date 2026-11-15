# Proof-of-Change go/no-go: 2026-11-15 on ef12096

4 report(s) in this folder: 1 need attention, 3 could not be verified, 0 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **NEEDS ATTENTION**: mahmoud/boltons#789: Reject NaN when rounding to an option. Probe: 2 observation(s) need attention: c3.ceil_nan_same differs although the claim says it does not (C3); c3.floor_nan_same differs although the claim says it does not (C3); probe: claim(s) C1, C2 proven; tests: 2 test(s) fail on main and pass on the PR; 18 test(s) ran on main, 19 on the PR; 1 new test(s) pass, 16 unchanged
- **COULD NOT VERIFY**: pallets/click#3921: Python 3.11 cleanups. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1425 test(s) ran on main, 1427 on the PR; 2 new test(s) pass, 1448 unchanged (23 of them skipped on both sides)
- **COULD NOT VERIFY**: PyCQA/isort#2791: Fix add_imports relocating a leading isort: skip import below the sorted block. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 179 test(s) ran on main, 179 on the PR; 0 new test(s) pass, 178 unchanged
- **COULD NOT VERIFY**: prettytable/prettytable#546: Escape LaTeX special characters in get_latex_string(). Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 281 test(s) ran on main, 281 on the PR; 0 new test(s) pass, 280 unchanged

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| NEEDS ATTENTION | mahmoud/boltons#789: Reject NaN when rounding to an option | Probe: 2 observation(s) need attention: c3.ceil_nan_same differs although the claim says it does not (C3); c3.floor_nan_same differs although the claim says it does not (C3); probe: claim(s) C1, C2 proven; tests: 2 test(s) fail on main and pass on the PR; 18 test(s) ran on main, 19 on the PR; 1 new test(s) pass, 16 unchanged | [PDF](boltons-789/REPORT.pdf) |
| COULD NOT VERIFY | pallets/click#3921: Python 3.11 cleanups | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1425 test(s) ran on main, 1427 on the PR; 2 new test(s) pass, 1448 unchanged (23 of them skipped on both sides) | [PDF](click-3921/REPORT.pdf) |
| COULD NOT VERIFY | PyCQA/isort#2791: Fix add_imports relocating a leading isort: skip import below the sorted block | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 179 test(s) ran on main, 179 on the PR; 0 new test(s) pass, 178 unchanged | [PDF](isort-2791/REPORT.pdf) |
| COULD NOT VERIFY | prettytable/prettytable#546: Escape LaTeX special characters in get_latex_string() | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 281 test(s) ran on main, 281 on the PR; 0 new test(s) pass, 280 unchanged | [PDF](prettytable-546/REPORT.pdf) |
