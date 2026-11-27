# Proof-of-Change go/no-go: 2026-11-27 on 748f814

5 report(s) in this folder: 1 need attention, 1 could not be verified, 3 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **NEEDS ATTENTION**: python-attrs/attrs#1673: Collect class-body attributes when these= is passed. 5 test(s) fail on main and pass on the PR; 467 test(s) ran on main, 467 on the PR; 0 new test(s) pass, 464 unchanged (2 of them skipped on both sides); probe: claim(s) C3, C6, C7 proven; probe model-probe2-rewrite is uninformative (uninformative: every observation is probe-broken (the same exception or skip value on both sides)); its matching results do not count; a probe rewrite cannot raise the verdict: without the rewrite it is needs_attention
- **COULD NOT VERIFY**: mahmoud/boltons#842: Fix `asciify` dropping diaeresis letters not in `DEACCENT_MAP` (Ë, ë, Ï, ï). Could not verify: claim(s) C4, C5, C7 expect a difference but no observation matches (1 test(s) fail on main and pass on the PR; 47 test(s) ran on main, 47 on the PR; 0 new test(s) pass, 46 unchanged; probe model-probe1-rewrite is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count)

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| NEEDS ATTENTION | python-attrs/attrs#1673: Collect class-body attributes when these= is passed | 5 test(s) fail on main and pass on the PR; 467 test(s) ran on main, 467 on the PR; 0 new test(s) pass, 464 unchanged (2 of them skipped on both sides); probe: claim(s) C3, C6, C7 proven; probe model-probe2-rewrite is uninformative (uninformative: every observation is probe-broken (the same exception or skip value on both sides)); its matching results do not count; a probe rewrite cannot raise the verdict: without the rewrite it is needs_attention | [PDF](attrs-1673/REPORT.pdf) |
| COULD NOT VERIFY | mahmoud/boltons#842: Fix `asciify` dropping diaeresis letters not in `DEACCENT_MAP` (Ë, ë, Ï, ï) | Could not verify: claim(s) C4, C5, C7 expect a difference but no observation matches (1 test(s) fail on main and pass on the PR; 47 test(s) ran on main, 47 on the PR; 0 new test(s) pass, 46 unchanged; probe model-probe1-rewrite is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count) | [PDF](boltons-842/REPORT.pdf) |
| VERIFIED | mahmoud/boltons#844: Preserve quantile precision when weighted terms underflow | 18 test(s) fail on main and pass on the PR; 28 test(s) ran on main, 47 on the PR; 19 new test(s) pass, 10 unchanged; probe: claim(s) C1, C5, C6, C8 proven | [PDF](boltons-844/REPORT.pdf) |
| VERIFIED | mahmoud/boltons#845: Measure elapsed time across daylight-saving changes in relative_time | 1 test(s) fail on main and pass on the PR; 18 test(s) ran on main, 18 on the PR; 0 new test(s) pass, 17 unchanged; probe: claim(s) C1, C3 proven | [PDF](boltons-845/REPORT.pdf) |
| VERIFIED | encode/httpx#3855: Normalize default ports for uppercase and mixed-case URL schemes | 6 test(s) fail on main and pass on the PR; 1 test(s) re-parametrized (1 -> 5 ids); 659 test(s) ran on main, 663 on the PR; 5 new test(s) pass, 652 unchanged; probe: 1 observation(s) shown as advisory only (the probe input may not reach the changed code; the tests already prove the change): c2.port_http_lower (C2); probe: claim(s) C2 proven | [PDF](httpx-3855/REPORT.pdf) |
