# Tavily credits are metered per check, and a credit cap refuses a check up front

## What changed

Every Tavily call a product check makes is now counted. A basic search costs 1 credit and an advanced one 2;
crawl and extract use the cost Tavily reports in the response. Each product record stores the totals under
`tavily_credits` (calls and credits per kind, plus the total), and the log prints one line:
`Tavily credits used: N (search ..., crawl ..., extract ...)`.

The repository crawl cache is already keyed by repository and base commit and kept on disk, so a second run of
the same pull request at the same commit makes no crawl or extract call and spends no crawl credits. Its
temporary file now carries the process id, so two runs writing the same entry at once cannot clash. A test runs
the crawl in two separate processes and checks that the second one is a cache hit with no Tavily call.

With `POC_TAVILY_CREDIT_CAP` set, a product check reads the account's current usage from Tavily's usage
endpoint before its first Tavily call. If one check's worst case (21 credits: setup searches, setup-gap and
related-report searches, an uncached crawl and an extract) would take usage past the cap, or past the plan
limit Tavily reports, the check stops at could not verify with "Tavily credit limit reached" and the numbers.
If the cap is set but the usage cannot be read, the check also refuses, because the cap cannot be confirmed.
Without the variable nothing changes.

## Why

Credits run out in the middle of a batch, and a check that hits the limit halfway reports "Tavily unavailable"
after it has already spent time and credits. Measuring the cost per check shows where credits go, and refusing
up front keeps a batch from ending in half-finished checks.

## What stays the same

Tavily stays required: a missing key still refuses, and a failed lookup still stops the check. No verdict
changes when the cap is unset. The key is never written into a record, a log line or a refusal.

## Trade-offs

The worst case is a fixed, conservative estimate, so a check may be refused while a few credits remain. A
failed search that Tavily answered is still counted, since it is billed.
