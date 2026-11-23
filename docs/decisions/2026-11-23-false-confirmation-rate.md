# False confirmations sit next to wrong passes

## What changed

The benchmark summary now states a false-confirmation rate beside the existing wrong-pass count.
A wrong pass is a verified result on a known regression, the count the summary already calls a wrong
approval. A false confirmation is a pull request the tool called verified when the hand check says it
is a real break. The hand check uses labels the records already store: `break` and `needs_attention`.

A pull request with several records counts once in both rates. A verified pull request with no hand
check is left out of the false-confirmation rate and counted on its own as unchecked. The same note
is printed for a folder of saved records (`python -m bench.report --records`). That command only reads
the records.

## Why

Wrong passes use the benchmark's known-regression label. A hand check can disagree with that label,
and a saved record often has a hand check without being in the regression list. The rate has to show
those confirmed mistakes without treating an unchecked verified pull request as a success or a failure.

## Decision

Keep the stored verdict. Do not rewrite a record. Count each pull request once. Use only the hand-check
labels already on the record. Leave a verified pull request with no hand check out of the denominator
and report how many were left out.

## Alternatives and tradeoffs

Counting every record would make one pull request that was checked twice look like two mistakes.
Putting unchecked pull requests in the denominator would treat a missing hand check as a pass.
Inventing a new hand-check label would not match the labels the records already use.

## What it means for you

The summary table is unchanged. Under it, each arm shows wrong passes, false confirmations, and how
many verified pull requests had no hand check. For a directory of saved records, the report also lists
every stored verdict, once per record and once per pull request.
