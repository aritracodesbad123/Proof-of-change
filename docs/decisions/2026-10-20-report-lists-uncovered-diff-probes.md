# The report lists differences no claim covers

## What changed

The report has a section, "Differences no claim covers", for differences found by a differential probe that no claim in the pull request covers.

## Why

Under the usual baseline those probes are shown, but they do not decide the verdict, so their differences were easy to miss in the claims table.

## Decision

List those differences in their own section. The section is for reading. It does not change the verdict.

## Alternatives and tradeoffs

- Leave the differences only inside the probe table. A reviewer can miss them.
- Let those differences decide the verdict. That would change results, which this change does not do.

## What it means for you

Open the report and read "Differences no claim covers" when a differential probe saw something no claim mentioned. The verdict line is unchanged by that section.
