# Log what each review costs

## What changed

Every review record, from both Proof-of-Change and the PatchGuru comparison runner, now carries a `cost` block:

- tokens sent to the AI (input), tokens it wrote back (output), and how many of those were "thinking" tokens;
- the price of those tokens at the Nebius list price (the source page is named inside the record);
- how many AI calls were made, counting retries, failed calls and PatchGuru's self-review step;
- how long the machine spent (total, and building and testing where those are measured).

A small script (`ops/cost_report.py`) adds these up for a set of run folders and reports two numbers per tool:
cost per PR attempted (every run, including the ones that could not verify) and cost per PR that ended with a final
verdict (the same spend divided only by runs that ended verified or needs attention).

## Why

To compare the two tools fairly we need to know not only how often they are right but what each answer costs.
A tool that is cheap per attempt but rarely reaches a verdict can be expensive per useful answer, which is why both
numbers are reported and why runs that could not verify still count toward the spend.

## Trade-offs

- Prices are list prices typed into the code, with the page they came from. If Nebius changes its prices the
  table must be updated by hand; account discounts are not included.
- A call that fails before the server answers (for example a timeout) is counted as a call, but its tokens are
  unknown, so its cost shows as zero and the record says the cost is incomplete.
- PatchGuru gives two results (before and after its self-review) from one set of AI calls; both records show the
  same cost, marked as shared, and the report counts it once.
- Today's runs were reconstructed from saved AI replies. Where no replies were saved, the report says so instead
  of guessing.
