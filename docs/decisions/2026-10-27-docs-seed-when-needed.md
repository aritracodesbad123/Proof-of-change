# The docs-site seed is crawled only when the repository gives too few setup steps

## What changed

A product check's repository crawl always crawls the repository seed (the pull request's repository at its
base commit) and extracts its key pages. It crawls the project's docs site, when the packaging metadata
labels one, unless those pages give at least `MIN_REPO_STEPS` (2) setup steps that the project's own files
back **and** at least one of them is an extra, a dependency group or a requirements file. Bare package names
alone, such as a README's `pip install requests attrs`, never skip the docs site: they list packages but do not
describe a test setup. The rule is the same for every project. No project has its own flag.

Each record's `repo_crawl` block now has `seed_decisions`: for every seed, its URL, whether it was crawled, and
why. Examples are "the repository seed is always crawled", "skipped: the repository gave 3 setup step(s), at
least 2, including 1 extra, group or requirements file", "the repository gave 0 setup step(s), fewer than 2"
and "the repository gave 2 setup step(s) but no extra, dependency group or requirements file". A check that reads a saved crawl records the
seeds that crawl used.

## Saved crawls stay valid

The cache key (repository, base commit, docs site) and `CRAWL_VERSION` are unchanged, so every crawl already
saved on disk is still hit and makes no Tavily call. A new entry only adds the optional `seed_decisions` field,
which an older reader ignores. A test writes an entry in the existing format under the existing key formula
and checks that it is hit with no crawl or extract call.

A saved crawl is still reused only for the same repository at the same base commit. Every new base commit pays
for a crawl.

## Credits

Tavily's published rules ([API credits](https://docs.tavily.com/documentation/api-credits)):

> Basic Search (`basic`): Each request costs 1 API credit.
>
> Basic Extract (`basic`): Every 5 successful URL extractions cost 1 API credit.
>
> Map with (`instructions`): Every 10 successful pages returned cost 2 API credits.
>
> Crawl Cost = Mapping Cost + Extraction Cost

With `limit` 40, `instructions` set and basic depth, one seed costs at most 40/10 x 2 + 40/5 = 16 credits. A
check that needs only the repository seed costs at most 8 (searches) + 16 + 3 (extract of 12 URLs) = 27. A
check that also needs the docs site costs at most 43. The credit cap (`POC_TAVILY_CREDIT_CAP`) still prices
43 up front, because a check cannot know before crawling whether it will need the docs site. The cap stays as
the backstop. Tests tie both numbers to the request bodies the code sends.

## Trade-offs

A project whose repository gives two or more backed setup steps, one of them structured, no longer has its
docs site read. If those steps are
incomplete, the setup-gap repair loop and its lookups still run as before. The docs pages are no longer sent to
Extract, since extract runs before the decision. When the docs seed is crawled, its raw page text still feeds
the setup steps.
