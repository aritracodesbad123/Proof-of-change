# Compare a merged pull request with its real base

Status: accepted

## What changed

A product check now makes sure the main side and the pull-request side are different code. When the main side would be the pull-request head itself, or a commit with the same tree, the check chooses the main side in this order: (1) the merge-base of the pull request's recorded base (GitHub base.sha) and its head; (2) if that merge-base is the head itself, the first parent of the pull request's merge commit (GitHub merge_commit_sha); (3) base.sha, only when the pull-request head is not already an ancestor of base.sha (otherwise base.sha would bring in base-branch commits that are not part of the pull request, so the check stops as unsupported). The first one with a different tree wins. Using the merge-base first means every commit of a multi-commit pull request is compared, and commits added to the base branch after the pull request branched off are not pulled in. There is no fallback to the parent of the head commit, because for a pull request with more than one commit that compares only its last commit. If none of the three gives different code, the check stops as could not verify with an "unsupported:" reason. A product check whose two sides are the same commit can no longer be called docstring-only or "holds by construction". It ends as could not verify, in every baseline mode, before the docstring-only rule is reached.

Study runs are unchanged.

## Root cause

For a pull request that is already merged or closed, GitHub no longer offers the test merge ref, so the check fell back to the merge-base of the head and the base branch. After a merge, the head is already part of the base branch, so the merge-base is the head itself. Both sides were the same commit. The docstring-only rule compares the changed files on the two sides, found them equal (they were the same files), and reported "docstring-only; behaviour claims hold by construction". The rule itself is correct: on the real base-to-head diffs of the affected pull requests it reports the changes as not equal.

## Alternatives and tradeoffs

- The rebase-merge gap is listed in docs/LIMITATIONS.md.

- Parent of the head commit as a fallback: dropped, because it compares only the last commit of a multi-commit pull request.

- Refuse every merged pull request: simpler, but loses checks that can still be run honestly against their base.
- Apply the same guard to study runs: left out so study results stay comparable; it can be a separate change.

## What it means for you

Merged or closed pull requests are tested against the code they were opened on. If that cannot be found, the result is could not verify with a clear reason instead of a false comments-only result.
