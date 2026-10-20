# The main study keeps all 92 pairs and labels each repository

## What changed

The ordered main-study list stays the 92 pairs already chosen. The scope of that list is Python repositories. Each repository also gets a descriptive label: `library`, `non_library`, or `unknown`. The label does not add or remove a pair, and the ordered list file is left as it is.

The rule is written down, and its SHA-256 is recorded, before the rule is applied. A repository is `library` only when the Python Package Index returns a project for that repository's name and the project's links point at the same GitHub repository. Any other answer from the index is `non_library`. If the index cannot be reached after three further tries, the label is `unknown`.

## Why

Those 92 pairs are the study. A later reader still needs to see which repositories are published libraries and which are not, without changing who is included. Judging that from the project's name would be a different decision for every reader. The package index page and the repository link are the same check every time.

## Decision

Keep every pair. Do not filter the list further.

Apply only the written rule. Do not rename a project so that it matches, and do not treat a familiar name as a library on its own. Store the label beside the pair. Leave the ordered list file unchanged.

## Alternatives and tradeoffs

Dropping repositories that are not libraries would shorten the list and change the study. The label is only a description, so the 92 pairs stay.

Matching on the project name alone would mark more repositories as libraries, including a project that shares a name with a different repository. The link back to the same GitHub repository is required.

## What it means for you

The ordered list is unchanged. Beside it, each pair has a label. `library` means the package index lists that repository name and links to that GitHub repository. `non_library` means the index answered and that link was not there. `unknown` means the index could not be reached.
