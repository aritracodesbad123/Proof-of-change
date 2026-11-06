# Proof-of-Change go/no-go: 2026-11-06 on 4050401

3 report(s) in this folder: 0 need attention, 2 could not be verified, 1 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **COULD NOT VERIFY**: pyinvoke/invoke#1097: Use command-line names in missing-argument errors. Could not verify: claim(s) C1, C2, C4 expect a difference but no observation matches (134 test(s) ran on main, 137 on the PR; 3 new test(s) pass, 135 unchanged (1 of them skipped on both sides); probe model-p1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count)
- **COULD NOT VERIFY**: Delgan/loguru#1515: Evaluate every rotation condition so a skipped one cannot fire spuriously. Unverified behaviour claim: "I left it untouched."; needs a probe (1 test(s) fail on main and pass on the PR; 149 test(s) ran on main, 149 on the PR; 0 new test(s) pass, 151 unchanged (3 of them skipped on both sides))

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| COULD NOT VERIFY | pyinvoke/invoke#1097: Use command-line names in missing-argument errors | Could not verify: claim(s) C1, C2, C4 expect a difference but no observation matches (134 test(s) ran on main, 137 on the PR; 3 new test(s) pass, 135 unchanged (1 of them skipped on both sides); probe model-p1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count) | [PDF](invoke-1097/REPORT.pdf) |
| COULD NOT VERIFY | Delgan/loguru#1515: Evaluate every rotation condition so a skipped one cannot fire spuriously | Unverified behaviour claim: "I left it untouched."; needs a probe (1 test(s) fail on main and pass on the PR; 149 test(s) ran on main, 149 on the PR; 0 new test(s) pass, 151 unchanged (3 of them skipped on both sides)) | [PDF](loguru-1515/REPORT.pdf) |
| VERIFIED | andialbrecht/sqlparse#944: fix: avoid ValueError on malformed CASE with reindent_aligned | 175 test(s) ran on main, 177 on the PR; 2 new test(s) pass, 177 unchanged (2 of them skipped on both sides); probe: claim(s) C2 proven | [PDF](sqlparse-944/REPORT.pdf) |
