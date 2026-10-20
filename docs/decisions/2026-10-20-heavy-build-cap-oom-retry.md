# Heavy source builds are capped, and an out-of-memory kill is retried

## What changed

Only a limited number of heavy source builds run at once. The default cap is 1. It can be raised, and it is also limited by memory: about one build per 8 GB. The compiler itself is kept to a small job count (default 1, about one job per 2 GB). If the compiler is killed for using too much memory (signal 9, or the line "Killed signal terminated program"), that build is tried once more. If it is killed again, the result is an infrastructure failure to retry, not a finding about the pull request.

## Why

Several large compiles at once, or one compile using every core, can be killed by the operating system for using too much memory. That kill is about the machine, not about the change under test.

## Decision

Take a slot before a heavy compile and release it afterwards. A timeout we impose ourselves is not treated as an out-of-memory kill. The infrastructure failure stays could not verify, and the report says to re-run. The cap is a host setting. Pull-request code does not receive it.

## Alternatives and tradeoffs

- Let every core compile at once. That is faster until the machine kills the compiler.
- Treat the kill as a failed build of the pull request. That blames the change for a lack of memory.

## What it means for you

Large compiles wait for a free slot. If one is killed for memory, it is retried once. A second kill is reported as an infrastructure failure to re-run, not as a result about the pull request.
