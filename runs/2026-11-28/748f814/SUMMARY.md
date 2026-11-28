# Proof-of-Change go/no-go: 2026-11-28 on 748f814

3 report(s) in this folder: 1 need attention, 1 could not be verified, 1 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **NEEDS ATTENTION**: PyCQA/isort#2810: Cache compiled known-module regex patterns across Config instances (#2805). Probe: 1 observation(s) need attention: c2.same_object does not differ although the claim says it does (C2); tests: 63 test(s) ran on main, 64 on the PR; 1 new test(s) pass, 64 unchanged (1 of them skipped on both sides)
- **COULD NOT VERIFY**: mahmoud/boltons#851: Classify decimal format fields consistently with Python. Could not verify: claim(s) C1, C4, C6, C7 expect a difference but no observation matches (15 test(s) fail on main and pass on the PR; 20 test(s) ran on main, 35 on the PR; 15 new test(s) pass, 5 unchanged; probe model-p1-rewrite is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count)

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| NEEDS ATTENTION | PyCQA/isort#2810: Cache compiled known-module regex patterns across Config instances (#2805) | Probe: 1 observation(s) need attention: c2.same_object does not differ although the claim says it does (C2); tests: 63 test(s) ran on main, 64 on the PR; 1 new test(s) pass, 64 unchanged (1 of them skipped on both sides) | [PDF](isort-2810/REPORT.pdf) |
| COULD NOT VERIFY | mahmoud/boltons#851: Classify decimal format fields consistently with Python | Could not verify: claim(s) C1, C4, C6, C7 expect a difference but no observation matches (15 test(s) fail on main and pass on the PR; 20 test(s) ran on main, 35 on the PR; 15 new test(s) pass, 5 unchanged; probe model-p1-rewrite is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count) | [PDF](boltons-851/REPORT.pdf) |
| VERIFIED | prettytable/prettytable#516: Clear active sorting when deleting its column | 1 test(s) fail on main and pass on the PR; 281 test(s) ran on main, 282 on the PR; 1 new test(s) pass, 280 unchanged; probe: claim(s) C3, C4, C5 proven | [PDF](prettytable-516/REPORT.pdf) |
