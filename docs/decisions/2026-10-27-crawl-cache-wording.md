# The crawl cache wording says it is reused only at the same repository and base commit

## What changed

Wording only. The credit-cap and repository-crawl decision notes, and the worst-case docstring in
`poc/tavily_budget.py`, now say that a saved crawl is reused only by a check of the same repository at the
same base commit. Every new base commit pays for a full crawl, including a newer tip of the same branch or
another pull request on a newer commit.

## Why

The earlier text could be read as "a project crawled recently is cheap to check again". The cache key is the
exact repository and base commit, so budget estimates must price a full crawl for every new base commit.

## What stays the same

No code path, cache key, credit figure or verdict changes.
