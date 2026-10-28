# Parse errors go back to the model; Tavily credits come from each response

## Probe parse repair

A probe whose code did not parse was dropped with "code does not parse: ... (line N)", and the only retry was the
generic "no usable probe" one, which did not show the model the error. A check could then end with no probe.

`poc/model_probes._repair_parse_errors` now asks the model to fix only the probes that do not parse, giving it,
for each, the exact SyntaxError message, line and column, the offending line, and the full code as received. It
tries at most `PARSE_REPAIR_TRIES` (2) times. A fixed probe replaces the broken one by id (or by position when the
reply has exactly as many probes); it still goes through `validate_probe` like any other. Every attempt is kept in
`parse_repairs` (attempt number, probe, error, outcome) and the record's probe plan shows it as
`model_parse_repairs`. The repair is model calls only and makes no web searches.

The cover retry's trail (`retried`, `unmatched_covers`) is now saved in the probe plan too
(`model_retried`, `model_unmatched_covers`), so a record shows whether it fired and why it was or was not kept.

The test uses a probe with the same error as the failed run ("unexpected character after line continuation
character", line 1). The run did not save the probe text, so the test rebuilds the same error.

## Tavily credits per call

The per-check total used to estimate searches from their depth and read the balance from the usage endpoint.
Searches now send `include_usage: true` (crawl and extract already did), and every answered call is kept in
`tavily_credits.calls` with its credits, `source` ("api" when the response's own `usage.credits` is present,
otherwise "estimate" at the published rate) and the `usage` block as returned. The totals add
`api_reported_credits` and `estimated_credits`, and the run log line shows both. A check that ends in a harness
error now still records and logs its credits.

## Follow-up: repairs change code only

A parse repair now keeps the original probe's claims, covers, expect and about, and takes only the new code. Repairs
are paired to originals by id only, never by position. A repair is rejected when it has fewer observation keys or
fewer looped inputs than the original. Both counts are read from the code text, so a broken original still counts.
