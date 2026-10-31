# An unshown differs claim is advisory once a related change is proven

## What changed

A claim that says behaviour changes, and whose covered observations all agree (the same value on both sides), no longer raises needs attention when another differs claim on the same record is already proven by a probe. Those agreeing observations are listed as advisory. The reason says the claim was not shown on these inputs, and a related change was proven.

Unchanged:

- A true contradiction still needs attention. That includes a claim that says the result stays the same but the observations differ, a difference no claim covers, a differs claim that is only partly shown, and a result that is stable on the base and unstable only on the pull request.
- When the record has no proven differs claim yet, agreeing observations under a differs claim still need attention, as they did before.
- A claim proven only as "the result stays the same" does not count as the related change.

## Why

On loguru pull request 1536, claims C1 and C2 were proven, while C3 and C4 agreed on every covered observation. On toolz pull request 654, claim C4 was proven, while C1, C3 and C5 agreed. Each agreeing result was scored as "does not differ although the claim says it does", so the check was needs attention. The probes had not shown those claims. They had not found a contradiction, and a related change was already proven.

## Decision

- The rule runs where probe findings are turned into the verdict. An observation is covered by the claim it was linked to.
- The claim qualifies only when every covered observation agrees: state "same", labelled needs human ("does not differ although the claim says it does"). Any other covered observation, including a difference, a contradiction, a flaky result, or a probe that did not run, leaves the claim alone.
- "Proven" means a probe observation labelled proven whose two sides differ, and that observation is not itself advisory or unstable only on the pull request. It has to be a different claim: a claim that was shown cannot also have every observation agree.
- The agreeing observations stay visible in the reason. They are not in the list of observations that need attention, so they do not make the verdict needs attention. The rest of the record decides, the same way an unchanged sub-check of an input that was shown already does.
- Their label on the observation stays needs human. The reason is what says they are advisory.

## Alternatives and tradeoffs

- Treating every agreeing differs claim as could not verify would keep a clean test run and a proven related change from being verified. The check did show a change.
- Treating agreeing observations as advisory even when nothing on the record is proven would hide a claim the probes never showed. That case still needs attention.
- Dropping the needs-human label would make the observation look like a plain "no difference" and hide that a differs claim was not shown. The label stays, and the reason carries the advisory wording.

## What it means for you

A check where some differs claims agree on every covered observation, and at least one other differs claim is proven, no longer says needs attention for those agreeing observations. The reason names them and says the claim was not shown on these inputs and a related change was proven. A check with no proven differs claim is unchanged.

## Offline proof

The fixtures under `tests/fixtures/agreeing_differs/` are the probe runs, claims, test comparison and coverage from the two records, trimmed to what the verdict reads. They contain no machine paths. `tests/test_agreeing_differs_when_proven.py` re-judges them with the current rules and checks the boundaries above. Nothing from the pull requests is run again.

The same rule also applies to an older recorded check, attrs pull request 1647. Claims C1 and C3 are proven, and both of C4's covered observations agree. That check is no longer needs attention. C4 stays labelled needs human, so linking the observation to the claim did not prove it.
