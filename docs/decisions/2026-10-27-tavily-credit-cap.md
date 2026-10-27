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

The repository crawl cache is keyed by the exact repository and base commit (plus the docs site and
`CRAWL_VERSION`) and kept on disk. A saved crawl is reused only by a later check of the same repository at the
same base commit; it then makes no crawl or extract call. Any new base commit, including a newer tip of the
same branch or another pull request on a newer commit, misses the cache and pays for a full crawl. Before crawling, a run now takes an exclusive
file lock (`fcntl`) on that cache entry and reads the cache again once it holds the lock. Of several runs that
start at the same moment, one crawls and writes the entry, and the others wait and read it. Each write goes to
its own temporary file from `tempfile.mkstemp`, so neither processes nor threads share one, and is then
renamed into place. Tests cover a later process (a cache hit) and two processes released at the same moment
(exactly one crawl). If the lock file cannot be opened, the crawl still runs unlocked, since the cache is only
a saving.

With `POC_TAVILY_CREDIT_CAP` set, a product check reads the account's current usage from Tavily's usage
endpoint before its first Tavily call. If one check's worst case (43 credits, derived below) would take usage past the cap, or past the plan
limit Tavily reports, the check stops at could not verify with "Tavily credit limit reached" and the numbers.
If the cap is set but the key is missing or the usage cannot be read, the check also refuses, because the cap
cannot be confirmed; with no key, `/usage` is never called.
Without the variable nothing changes.

## How the worst case is derived

Tavily's published rules ([API credits](https://docs.tavily.com/documentation/api-credits)):

> Basic Search (`basic`): Each request costs 1 API credit.
>
> Basic Extract (`basic`): Every 5 successful URL extractions cost 1 API credit. Advanced Extract (`advanced`):
> Every 5 successful URL extractions cost 2 API credits.
>
> Regular Mapping: Every 10 successful pages returned cost 1 API credit. Map with (`instructions`): Every 10
> successful pages returned cost 2 API credits.
>
> Crawl Cost = Mapping Cost + Extraction Cost

The code applies these rules to the request bodies it really sends:

- Searches, all basic: 3 setup queries, 3 setup-gap repair tries plus the batch gate search, and 1
  related-reports search, for 8 credits.
- Crawl, per seed: `limit` 40, `instructions` set, `extract_depth` basic. Mapping is 40/10 x 2 = 8 and
  extraction is 40/5 x 1 = 8, so 16 credits. A repository with a docs site has 2 seeds, so 32.
- Extract: at most 12 URLs at basic depth, so ceil(12/5) = 3 credits.
- Total: 8 + 32 + 3 = **43 credits**.

A test builds the crawl and extract bodies through the same functions the live calls use. It prices them
with this formula, checks it against the docs' own examples (10 pages basic = 3, advanced = 5), and ties the
search counts to the setup queries and the repair-try limit. If a limit or a depth changes, the worst case
changes with it.

A crawl that returns fewer pages costs less: 10 crawled pages and 8 extracted cost
ceil(10/10) x 2 + ceil(10/5) + ceil(8/5) = 6 by this rule. Tavily reported 5 for such a run, so the formula is
an upper bound.

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
