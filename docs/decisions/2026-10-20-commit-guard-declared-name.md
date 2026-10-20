# The commit check uses the name the project declares

## What changed

After a source checkout is installed, the wrong-commit guard reads the install record (`direct_url.json`, the file that says where an install came from) and checks that the installed commit is the one requested. It used to look that record up under the library label. When a repository's label is not the name it installs under, there is no matching install record, and the comparison stops as "could not verify".

The guard now does one more lookup in that case. If the label has no installed distribution, it reads the distribution name the checkout declares in `pyproject.toml` under `[project] name`, and checks that name instead. The result records the name that was checked.

## Why

Some repositories install under a different name from their label. The zarr-python repository installs the distribution `zarr`. Both sides install, but the guard looks for `zarr-python`, finds no `direct_url.json`, and stops the comparison.

## Decision

- Look up the label first.
- If that label has no installed distribution, and the checkout declares a different `[project] name`, check the declared name.
- Record that name as the distribution the guard checked.
- Do not use the declared name when the label itself is installed. A missing install record, an install from another directory, or an install of another commit still fails.

## Alternatives and tradeoffs

Always guessing from the repository name would fix the one known repository and miss the next one. The name in `pyproject.toml` is the name the project says it installs under.

Using the declared name even when the label is already installed would let a second distribution stand in for an install that has no commit to check. The guard stays closed in that case.

## What it means for you

A source comparison of a project whose label differs from its installed name can get past the commit check when the installed commit is the one requested. If the install is missing, comes from another directory, or is another commit, the comparison still stops and says why.
