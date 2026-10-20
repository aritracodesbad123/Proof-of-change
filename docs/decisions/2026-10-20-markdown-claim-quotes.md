# Claim quotes ignore markdown marks

## What changed

Before a claim quote is checked against the pull-request title and description, markdown is removed from both. That covers code fences, inline code marks, links, and emphasis.

## Why

A quote copied from the pull request often keeps the backticks or the bold marks, or the pull request has them and the quote does not. The words were the same, but the check said the quote was not in the text.

## Decision

Remove those marks, then compare the words. A quote with backticks matches the same words without them, and the other way around. The link address is dropped and the link text is kept.

## Alternatives and tradeoffs

- Compare the raw text. Real quotes would be rejected because of marks that are not part of the claim.
- Require the model to copy the marks exactly. Small differences in marks would still reject a true quote.

## What it means for you

A claim is kept when its words appear in the pull request, whether or not either side wrapped them in markdown.
