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

## Addendum: computer time has a price too, and a fair side-by-side view

AI tokens are only part of the bill: building the library and running its tests keeps a machine busy, which also
costs money. Every record now shows three amounts: AI cost, computer cost and total cost.

- **How computer time is priced.** At an hourly rate for a cloud machine like the one our runs use (8 Intel
  vCPUs, about 16 GiB of memory). We matched Nebius's CPU-only Intel Ice Lake machine, preset "8vcpu-32gb", the
  smallest one with 8 vCPUs: 8 x $0.012 per vCPU-hour + 32 x $0.0045 per GiB-hour = **$0.24 per hour**. Source:
  Nebius compute pricing page, https://docs.nebius.com/compute/resources/pricing, checked 13 Oct 2026 (prices in
  effect from 1 Oct 2026). The rate can be changed with the `POC_MACHINE_USD_PER_HOUR` setting.
- **Trade-off.** That preset has twice our memory, so it slightly over-prices computer time; it is the closest
  published machine. Only time inside a review is priced; idle time between runs and disk space are not.
- **Matched comparison.** The two tools did not try the same set of PRs, so their overall totals are not a fair
  comparison. The report now has a separate section with only the PRs both tools attempted, and keeps the all-runs
  totals in their own section.
- **Verdict rate.** Next to "cost per PR with a final verdict" the report shows the verdict rate (PRs that got a
  final verdict divided by PRs attempted), because a low cost per verdict means little if few PRs get one.
- **Tying AI spend to runs.** Our tool saves AI replies per mode folder, not per PR, so for today's runs a reply is
  tied to the PR whose run time contains it. Replies that fit no run still count in the all-runs totals and are
  listed as "not tied to a run". New records carry their own cost, so this guess is only needed for today.
