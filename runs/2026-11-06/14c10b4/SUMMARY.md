# Proof-of-Change go/no-go: 2026-11-06 on 14c10b4

2 report(s) in this folder: 0 need attention, 2 could not be verified, 0 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **COULD NOT VERIFY**: pyinvoke/invoke#1097: Use command-line names in missing-argument errors. Could not verify: claim(s) C2 expect a difference but no observation matches (134 test(s) ran on main, 137 on the PR; 3 new test(s) pass, 135 unchanged (1 of them skipped on both sides); rejected: claim pattern(s) C1, C2 match none of this probe's observation names, so the probe is not counted)
- **COULD NOT VERIFY**: Delgan/loguru#1515: Evaluate every rotation condition so a skipped one cannot fire spuriously. Could not verify: claim(s) C1, C3, C4 expect a difference but no observation matches (1 test(s) fail on main and pass on the PR; 149 test(s) ran on main, 149 on the PR; 0 new test(s) pass, 151 unchanged (3 of them skipped on both sides); probe model-probe-a is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-probe-b-rewrite is not_adequate (ran none of the 1 changed line(s) on the main side); its results do not count either way)

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| COULD NOT VERIFY | pyinvoke/invoke#1097: Use command-line names in missing-argument errors | Could not verify: claim(s) C2 expect a difference but no observation matches (134 test(s) ran on main, 137 on the PR; 3 new test(s) pass, 135 unchanged (1 of them skipped on both sides); rejected: claim pattern(s) C1, C2 match none of this probe's observation names, so the probe is not counted) | [PDF](invoke-1097/REPORT.pdf) |
| COULD NOT VERIFY | Delgan/loguru#1515: Evaluate every rotation condition so a skipped one cannot fire spuriously | Could not verify: claim(s) C1, C3, C4 expect a difference but no observation matches (1 test(s) fail on main and pass on the PR; 149 test(s) ran on main, 149 on the PR; 0 new test(s) pass, 151 unchanged (3 of them skipped on both sides); probe model-probe-a is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-probe-b-rewrite is not_adequate (ran none of the 1 changed line(s) on the main side); its results do not count either way) | [PDF](loguru-1515/REPORT.pdf) |
