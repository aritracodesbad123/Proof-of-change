# Proof-of-Change go/no-go: 2026-11-11 on ef12096

2 report(s) in this folder: 0 need attention, 0 could not be verified, 2 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

Nothing needs attention: every report is VERIFIED.

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| VERIFIED | mahmoud/boltons#758: Fix isoparse hour only timezone | 1 test(s) fail on main and pass on the PR; 17 test(s) ran on main, 17 on the PR; 0 new test(s) pass, 16 unchanged; probe: 4 unchanged sub-check(s) of an input where the claim's change was seen, shown as advisory only: c1.offset_minus08 (C1); c1.offset_plus05 (C1); c2.offset_minus08 (C2); c2.offset_plus05 (C2); probe: claim(s) C1, C2 proven | [PDF](boltons-758/REPORT.pdf) |
| VERIFIED | mahmoud/boltons#760: Preserve ManyToMany relationships across subclasses | 2 test(s) fail on main and pass on the PR; 100 test(s) ran on main, 100 on the PR; 0 new test(s) pass, 98 unchanged; probe: 2 unchanged sub-check(s) of an input where the claim's change was seen, shown as advisory only: c1.indep (C1); c1.inv_sep (C1); probe: 2 observation(s) shown as advisory only (claim not shown on these inputs; a related change was proven): c2.data_empty (C2); c2.inv_shared (C2); probe: claim(s) C1, C3 proven; probe: 1 probe(s) could not run on either side | [PDF](boltons-760/REPORT.pdf) |
