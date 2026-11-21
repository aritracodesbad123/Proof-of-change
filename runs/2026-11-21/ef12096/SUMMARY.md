# Proof-of-Change go/no-go: 2026-11-21 on ef12096

3 report(s) in this folder: 1 need attention, 2 could not be verified, 0 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **NEEDS ATTENTION**: python-attrs/attrs#1656: Fix 1424 attribute in these. Probe: 6 observation(s) need attention: c2.A.alias_correct differs although the claim says it does not (C3); c2.A.settings_preserved differs although the claim says it does not (C2); c2.B.alias_correct differs although the claim says it does not (C3); c2.B.settings_preserved differs although the claim says it does not (C2); probe model-probe1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; tests: 15 test(s) fail on main and pass on the PR; 295 test(s) ran on main, 295 on the PR; 0 new test(s) pass, 280 unchanged
- **COULD NOT VERIFY**: mahmoud/boltons#818: Fixes #814. Could not verify: claim(s) C4 expect a difference but no observation matches (1 test(s) fail on main and pass on the PR; 18 test(s) ran on main, 18 on the PR; 0 new test(s) pass, 17 unchanged; probe: 6 difference(s) no linked claim covers, shown as advisory only: c4.correct__1_h_3_0_m_, c4.correct__1_h_3_0_m_1_5_s_, c4.correct__1_m_3_0_s_, c4.correct__1_w_2_d_ (+2 more); probe: claim(s) C1, C2, C3 proven)
- **COULD NOT VERIFY**: mahmoud/boltons#820: Allow self fields in namedlist constructors. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 6 test(s) fail on main and pass on the PR; 75 test(s) ran on main, 76 on the PR; 1 new test(s) pass, 69 unchanged

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| NEEDS ATTENTION | python-attrs/attrs#1656: Fix 1424 attribute in these | Probe: 6 observation(s) need attention: c2.A.alias_correct differs although the claim says it does not (C3); c2.A.settings_preserved differs although the claim says it does not (C2); c2.B.alias_correct differs although the claim says it does not (C3); c2.B.settings_preserved differs although the claim says it does not (C2); probe model-probe1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; tests: 15 test(s) fail on main and pass on the PR; 295 test(s) ran on main, 295 on the PR; 0 new test(s) pass, 280 unchanged | [PDF](attrs-1656/REPORT.pdf) |
| COULD NOT VERIFY | mahmoud/boltons#818: Fixes #814 | Could not verify: claim(s) C4 expect a difference but no observation matches (1 test(s) fail on main and pass on the PR; 18 test(s) ran on main, 18 on the PR; 0 new test(s) pass, 17 unchanged; probe: 6 difference(s) no linked claim covers, shown as advisory only: c4.correct__1_h_3_0_m_, c4.correct__1_h_3_0_m_1_5_s_, c4.correct__1_m_3_0_s_, c4.correct__1_w_2_d_ (+2 more); probe: claim(s) C1, C2, C3 proven) | [PDF](boltons-818/REPORT.pdf) |
| COULD NOT VERIFY | mahmoud/boltons#820: Allow self fields in namedlist constructors | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 6 test(s) fail on main and pass on the PR; 75 test(s) ran on main, 76 on the PR; 1 new test(s) pass, 69 unchanged | [PDF](boltons-820/REPORT.pdf) |
