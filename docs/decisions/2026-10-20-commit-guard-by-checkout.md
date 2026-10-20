# The commit check matches the checkout folder

## What changed

After each side of a source comparison is installed, the wrong-commit guard reads the install record
(`direct_url.json`, the file that says where an install came from) and checks that the installed commit is the
one that was requested. It used to look that record up under a name taken from the repository name. When the
project installs under a different name, there is no matching record, and the comparison stops as "could not
verify".

The guard now looks at every installed distribution in that side's environment. It keeps the ones whose
install record names this side's checkout folder. The record's address is a `file://` path (a path on this
machine). The two paths are compared after symbolic links are resolved, so a link and the folder it points at
count as the same place. Exactly one distribution must match. The guard then checks that the checkout's
current commit is the commit that was requested. If the install record also names a commit, that commit must
be the same one. The result records the distribution name that matched.

A separate read-only program, `scripts/guard_dry_run.py`, can install both sides of each pair and run either
this check or the previous name check, then write a table. It does not run tests, probes, or model calls, and
it does not produce a verdict.

## Why

Some projects install under a name that is not the repository name. The zarr-python repository installs as
zarr. sentry-python installs as sentry-sdk, and that name is only in `setup.py`. Other projects put the name
only in `setup.cfg`, or only in the Poetry table of `pyproject.toml`. Names such as sb3-contrib and olive-ai
are the installed name, not the repository name. Reading one more file catches the projects that use that
file and misses the next one.

The install record already says which folder was installed. That folder is the checkout this run just built,
whatever the project calls itself.

## Decision

- Match the installed distribution by the checkout folder recorded in `direct_url.json`, not by a name.
- Exactly one distribution must point at that folder. Zero, or more than one, stops the comparison.
- The checkout's current commit must be the requested commit. A commit named in the same install record must
  be that commit too.
- An install from a different folder, or of a different commit, still stops the comparison and says why.
- Record the distribution name that matched.
- Keep the previous name lookup available to the dry-run program, so the two checks can be compared. A source
  comparison uses the folder check.

## Alternatives and tradeoffs

Guessing the name from `pyproject.toml`, then from `setup.py`, `setup.cfg`, or Poetry, fixes each project
whose name lives in a file the guesser knows. The next project stores it somewhere else, and a guessed name
can select the wrong distribution when two are installed. The folder in the install record does not depend on
where the name was written.

Stopping when two distributions point at the same folder refuses a case that might have been safe. It also
refuses to pick one of them by name. The comparison stays closed until there is a single install to check.

The dry-run program installs both sides and stops. It does not say whether the change is good. That table
only shows whether the commit check can see the install.

## What it means for you

A source comparison of a project whose repository name is not its installed name can get past the commit
check when the installed folder and commit are the ones requested. If nothing points at the checkout, two
distributions do, the folder is a different one, or the commit is a different one, the comparison still stops
and says why. The recorded distribution name is the one that was installed, not the repository name.
