# A published project can be labelled a library under another name

## What changed

The revised label still describes each repository. It does not add or remove a pair, and the ordered list stays as it is. The first written rule and the first labels stay in the study folder as history.

The first rule asked the package index only for the repository's own name. A project published under a different name was marked `non_library` even when that project's page links back to the same GitHub repository.

The revised rule reads the names the repository itself declares, then tries the repository name. It searches the whole default branch, so a repository that holds more than one package is included. A repository is `library` when any of those projects links back. The project name and the place the name was found are stored with the pair.

## Why

The label is there so a reader can see which of the 92 pairs are published libraries. Judging that only by the repository name missed libraries that publish under another name. The package index has no search by repository address, so the names have to come from the repository's own packaging files, in a fixed order, before the repository name is tried.

## Decision

Keep every pair. Do not filter the list.

Apply the revised rule as written, and record its SHA-256 before applying it. Do not invent a project name that the packaging files do not declare. Do not treat a familiar name as a library on its own. If a request fails, try it once more, then mark that repository `unknown` and say so.

Leave the first rule and the first labels untouched.

## Alternatives and tradeoffs

Staying with the first rule keeps the earlier labels stable and keeps missing libraries that do not share the repository's name.

A hand-kept list of project names would catch the known cases and would be a different list for every editor. The packaging files are the source instead.

Searching the index by the GitHub address would be direct. The index does not offer that search.

## What it means for you

The ordered list is unchanged. The revised labels sit beside the first ones. `library` means some project, under a name the repository declares or under the repository name, links to that GitHub repository. `non_library` means every candidate was answered and none linked back. `unknown` means a request failed twice.
