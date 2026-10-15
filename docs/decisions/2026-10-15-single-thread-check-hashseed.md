# The single-thread check no longer trips over the fixed hash seed

## What changed

Each report checks that the run limited every library to one thread. That check now looks only at the
thread-count settings, which must all be 1. The fixed hash seed, which is recorded in the same place, is checked
separately and must be 0.

## Why

On 15 Oct, 16 of 27 pull requests were marked "could not verify" because this check failed. Nothing was wrong
with the runs: every thread setting was 1. Since the day before, the record also holds the fixed hash seed
(PYTHONHASHSEED=0), and the check expected every value in that block to be 1, so the 0 made it fail.

## Trade-offs

None for the results: the same settings are still required. A record without any thread setting still fails.
