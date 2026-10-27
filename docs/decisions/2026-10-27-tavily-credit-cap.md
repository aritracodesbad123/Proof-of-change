# Tavily credits are metered per check, and a credit cap refuses a check up front

## What changed

Every Tavily call a product check makes is now counted. A basic search costs 1 credit and an advanced one 2;
crawl and extract use the cost Tavily reports in the response. Each product record stores the totals under
`tavily_credits` (calls and credits per kind, plus the total), and the log prints one line:
`Tavily credits used: N (search ..., crawl ..., extract ...)`.

The meter belongs to one check: `test_pr` starts it and `finish` takes it. Calls from any thread count toward
the running check, so the parallel side preparation of one check adds up. Checks in one process run one after
another (the console starts each check in its own process). If a second check ever started before the first
was taken, both totals are marked `overlapped` rather than silently mixed.

The repository crawl cache is keyed by repository and base commit and kept on disk, so a later run of the same
pull request at the same commit makes no crawl or extract call. Before crawling, a run now takes an exclusive
file lock (`fcntl`) on that cache entry and reads the cache again once it holds the lock. Of several runs that
start at the same moment, one crawls and writes the entry, and the others wait and read it. Each write goes to
its own temporary file from `tempfile.mkstemp`, so neither processes nor threads share one, and is then
renamed into place. Tests cover a later process (a cache hit) and two processes released at the same moment
(exactly one crawl). If the lock file cannot be opened, the crawl still runs unlocked, since the cache is only
a saving.

With `POC_TAVILY_CREDIT_CAP` set, a product check reads the account's current usage from Tavily's usage
endpoint before its first Tavily call. If one check's worst case (19 credits: 3 setup searches, 3 setup-gap
searches plus the batch gate search, 1 related-reports search, 2 crawl seeds of up to 40 pages at 4 credits
each, and 1 extract of up to 12 pages at 3 credits; a test ties each term to the code's own limits) would take usage past the cap, or past the plan
limit Tavily reports, the check stops at could not verify with "Tavily credit limit reached" and the numbers.
If the cap is set but the key is missing or the usage cannot be read, the check also refuses, because the cap
cannot be confirmed; with no key, `/usage` is never called.
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
