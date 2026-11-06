# Compare a pull request that is behind its target at the merge-base

## What changed

When a pull request is behind the base that was recorded for it, the check compares the merge-base of that
base and the pull-request head with the head. It does not compare the target tip with the head, and it does
not check the base out at the tip.

The recorded base is GitHub's `base.sha` or a SHA the caller passed (`--base-sha`, or the base named for the
pull request). GitHub's API returns the tip of the target branch in `base.sha`. That tip is not the fork.
`git merge-base` of the two commits, from the repository's own history, is the fork. Only those two commits
are consulted. A newer tip of some other branch is never written in over them.

A recorded base that is already an ancestor of the head is kept. That includes an older branch tip the pull
request is not behind, and it includes the fork itself when the caller passes that SHA. The fetched target
tip does not replace it.

The diff stored for the check is `git diff` of the commits that are checked out. Changed-line attribution
reads that diff: a context line, including a `skipif` marker the diff did not edit, is not a changed line.
The same checkout is the base tree for setup, for running the pull request's new or edited tests on the base,
and for the source a new probe is written against.

A pull request that is not behind its target still uses the target tip against GitHub's test merge when that
merge ref exists. At that point the tip is the fork, so the merge commit's tree matches the head.

The rule that installs the pull request's own dev extras, and that drops a package the pull request declares
from the main side's constraints, is unchanged. It still applies when the pull request's tree really changes
a pin relative to this base. It is not what decides which commit the base is.

## Why

A two-dot diff of the target tip against the pull-request head treats every commit the target branch added
after the fork as a change the pull request made in reverse. A pin the target bumped looks like the pull
request lowered it. A `skipif` the target edited looks like the pull request edited it. Setup then reads the
tip's declarations, new tests run against the tip, and a probe is written from the tip, so the base under
test is not the tree the pull request was written against.

The merge-base diff does not contain those target-only edits. Both checkouts of an untouched file match the
fork, so the changed-line set for that file is empty. Setup reads the fork's pins. The new tests and the
probe source read that same tree.

Using the test merge instead (tip versus a merge of the head into the tip) also keeps a target-only edit out
of the diff, because the edit is on both sides. It still tests the tip's tree. That rewrites what the base
is whenever the pull request is behind. The merge-base does not.

## Decision

- If the recorded base and the head have diverged, the comparison base is their merge-base and the pull-request
  side is the head. The diff, the changed lines, the base setup, the new tests run on the base, and the probe
  source all use that pair.
- If the recorded base is an ancestor of the head, keep it. Do not replace it with a newer tip.
- If the history cannot be read, keep the recorded base. Do not guess a tip.
- If the head is already contained in the recorded base, leave the existing distinct-base rule to decide.
  This change does not invent a parent commit.
- Do not add a case for any repository, pull request, or package name.

Verdict rules are unchanged. Stored records and tallies are unchanged.

## Alternatives and tradeoffs

Comparing the tip with GitHub's test merge stays the path for a pull request that is not behind, because the
tip is then the fork. Using it for a pull request that is behind would make setup, new tests, and probes see
target-branch edits the pull request did not make.

Replacing every older SHA with the current target tip would test the wrong base for a pull request that
correctly targets an older branch. Ancestry is what decides, not which SHA is newer.

Dropping the pull request's own dev-extra install would hide a pin the pull request really changed. That
install stays. It now sees the fork's declarations on the base side, so a pin only the target changed is the
same on both sides and is not rewritten.

## What it means for you

A pull request that is behind its target is tested against the fork, not against later target-branch edits.
A pin or a `skipif` that only the target changed is not reported as a pull-request change, and the base
install matches that fork. A pull request that targets an older base, and is not behind it, still uses that
base after the repository's other branches have moved.

## Offline proof

`tests/test_behind_target_base.py` builds two histories. In the first, the target moves after the fork and
edits a pin and a `skipif`; the selected commits are the fork and the head, the diff's changed lines do not
include that `skipif`, and setup reads the fork's pin. Passing the fork itself still selects the fork when a
newer tip exists. In the second, the pull request is not behind an older base while another branch has moved;
the older base is kept. Nothing from a live pull request is run.
