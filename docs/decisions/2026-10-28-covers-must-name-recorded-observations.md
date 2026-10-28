# Claim covers must name observations the probe code records

## Problem

A model probe lists, for each claim, the observation names it covers. In saved runs, some covers named no
observation the probe code ever records (the code printed "c2.first_col.row0" while the cover said
"c1.row0.first_col"). The claim then sees nothing and the real differences look unclaimed, so the check needs
attention for a naming slip rather than for a behaviour change. Judging cannot repair this afterwards without
guessing names, and guessing would hide differences no claim covers.

## Decision

At probe-writing time, before anything is frozen or run:

1. `recorded_names(code)` reads the names the code can record: string keys of dict literals and of subscript
   stores, and the constant start of f-string keys. If the code stores under any other kind of key, nothing is
   judged (no guess).
2. `unmatched_covers(probe)` lists covers that can match none of those names. A cover that is only the claim's own
   id ("C1", "C1.*") is left out: judging already links it by id.
3. If any usable probe has such a cover, the probes are asked for once more, with the reason. The retry is kept
   only when it is usable, links at least the same claims and leaves fewer unmatched covers; otherwise the first
   answer is kept, so no probe or link is lost. Covers still unmatched are recorded on the plan.
4. The probes prompt asks that every cover be a printed name or a pattern over them, and that a claim's
   observations start with its id in lower case.

Judging is unchanged: no difference becomes quieter, and the guard tests are untouched.

## Effect

Saved records keep their frozen probes, so re-judging them changes no verdict. In the saved offline set, 7 of 133
model probes (4 records) have a cover that names nothing their code records; across all saved records, 28 of 588
probes (18 records). The effect shows only on a new run.

## Keeping a retry

The retry is kept only when it weakens nothing: (a) at least as many usable probes, (b) for each claim at least
as many observation names matched by its covers (a probe whose names cannot be read adds none), and (c) fewer
unmatched covers, where a cover that is only the claim id ("C1.*") counts as unmatched, so trading a real name
for the id is not an improvement. It must also link every claim the first answer linked. Otherwise the first
answer is kept and the reason is recorded. The retry is one extra model call only; it makes no web searches and
costs 0 search credits.
