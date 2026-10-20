# The main-study pair list skips a missing patch and stays in one order

## What changed

Gathering the main-study pairs now skips a candidate whose patch file is missing, empty, or not a diff, and it
writes down why. It does not create a patch, and it does not rebuild one from the pull request.

A pair is kept only when the checks in the rules file all pass. The rules file sets a cap of 175 and a shuffle
seed of 20261020. The program writes the ordered list, a manifest that counts every exclusion and names the
reason for each one, and a SHA-256 hash of the list file and of the rules file. Running it twice on the same
candidates and the same rules writes the same list.

Columns that carry an expected verdict or a label are refused before any cell is used. A file whose name
contains "answers" is refused the same way.

Setup now stops when `g++` is not installed, and each run records the `g++` version on its machine record. That
compiler is what pandas needs in order to build. The recorded version does not change a verdict.

## Why

The expansion stopped when a patch file was not on disk. Filling that gap by inventing a patch would make the
pair look real when the diff was never supplied. Leaving the crash in place meant the list could not be
produced at all.

The list also has to be the same list if it is built again. A new shuffle each time, or a quiet drop with no
reason, would make it impossible to see which pairs were kept and why the others were not.

## Decision

Keep the matching checks as they are. Do not loosen them to reach 175. If fewer candidates pass, the list is
shorter.

A candidate matches only when all of these are true:

- The repository is one name of the form owner/name.
- The two pull request numbers are different.
- Both patch files are present, not empty, and are unified diffs.
- The two diffs name at least one changed file in common.
- The same pair has not already been kept.

The kept pairs are sorted by repository and pull request number, shuffled with seed 20261020, and cut at 175.
Pairs past the cap are listed as excluded, with the reason `over_cap`. A missing patch is `missing_patch`, and
the side (the agent pull request or the human pull request) is recorded. Other skips are `empty_patch`,
`not_a_diff`, `different_repo`, `same_pull_request`, `duplicate`, and `no_shared_file`.

The rules file must keep "rebuild a missing patch" turned off. The tool will not run if that switch is on.

Setup checks that `g++` is on the path and prints its version. The machine record stores that same version
line, or nothing when the compiler is absent. Older records stay valid without the field.

## Alternatives and tradeoffs

Rebuilding a missing patch from the pull request would let more pairs through, and it would hide the fact that
the supplied file was absent. The list would then depend on a network read, and a later reader could not tell a
supplied diff from a reconstructed one.

Dropping the cap, or treating "no file in common" as a match, would make a longer list by changing who
qualifies. The cap stays 175, and a pair with no file in common stays out.

Failing the whole expansion on the first missing file is what already happened. Skipping that one candidate
keeps every other pair that does have its patches.

## What it means for you

Prepare a CSV with the columns `repo`, `agent_pr`, `human_pr`, `agent_patch`, and `human_patch`. Patch paths
are relative to the CSV's directory, or to `--root`. Do not add verdict or label columns, and do not put
"answers" in the file name.

Then run:

```
python -m evals.gather_study_pairs \
  --candidates <candidates.csv> \
  --rules evals/study_pair_rules.json \
  --out evals/study_pairs/main-study-pairs.json \
  --manifest evals/study_pairs/manifest.json
```

The command prints how many pairs matched, the exclusion counts, and both hashes. The manifest has one line
per excluded candidate. If `g++` is missing, `make setup` stops and tells you to install it before continuing.
