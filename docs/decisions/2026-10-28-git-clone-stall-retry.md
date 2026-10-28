# A stalled git clone gives up early and is retried; fetches are left alone

A stalled download used to hold a check for the whole step timeout (up to 15 minutes) before it failed.

Now only `git clone` gets a low-speed limit (`http.lowSpeedLimit=1000`, `http.lowSpeedTime=60`: under 1 KB/s for 60 s gives up). `clone_with_retry` in `ops/daily_run.py` removes the partial folder and retries a failed clone up to 3 times with the limit, then makes one last attempt without it, bounded only by the step timeout. So a repo that is slow to pack still clones, and a truly stalled one costs a few minutes instead of 15. Every clone (both sides from git, a pinned clone, the packaging checkout) goes through it.

Fetches never get the limit. GitHub can send nothing for a long time while it packs a large repo, and a failed `pull/N/merge` fetch switches the comparison to a merge-base basis, so cutting a fetch short could quietly change what is compared. That fetch is now also retried once before the fallback is used; the fallback and its recorded basis are unchanged.

It does not change any verdict.
