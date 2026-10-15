# Model-written probes: always import json, and ask again when no probe names a claim

## What changed

1. Every model-written probe file now starts its code with `import json`, added by the tool itself.
2. When the pull request has testable claims but none of the model's probes says which claim it checks, the tool
   asks the model once more, saying exactly what was missing. If the second answer still links no claim, the first
   answer is kept as it was.

A probe is a small script that runs the same inputs on the old code and on the new code; plain code then compares
what it printed. A claim is one statement in the pull request description about how behaviour changes (or stays
the same).

## Why

Two problems showed up in live runs on real pull requests.

- **Missing import.** The probe contract says the last printed line must be a JSON object. The model sometimes
  wrote `print(json.dumps(...))` without `import json`. Python then stopped with a `NameError` on both sides, so
  every probe for that pull request "could not run" and tested nothing. The tool then had no evidence about the
  change at all, even though the probe logic itself was fine.
- **Probes not linked to claims.** The model sometimes wrote good probes that exercised exactly the claimed fix,
  but left each probe's `claims` list empty. The tool then saw a real, intended difference that "no claim covers"
  and reported it as needing attention. That is a false alarm caused by missing bookkeeping, not by the code under
  review.

## Decision

- Add the import in the tool. It is one line, it cannot change the behaviour of the library being tested, and it
  removes a whole class of wasted probe runs.
- Treat "testable claims exist, but no probe names any of them" as an answer worth one more try, the same way an
  empty or invalid answer already is. The retry uses the same inputs (the pull request text and the old-side code
  only) and the same checks. A retry is only used if it passes the checks and links at least one claim.

## Alternatives and tradeoffs

- **Fix the prompt only.** We could remind the model harder to import json and to fill in `claims`. Prompts reduce
  the problem but do not remove it; the import in particular is cheaper and more reliable to add in code.
- **Reject unlinked probes.** We could throw away any probe that names no claim. We chose not to: a probe without
  claims can still catch an unannounced change, which is one of the main things this tool looks for. Only when
  *every* probe is unlinked do we ask again, and we never lose the first answer.
- **Cost.** The retry adds one more model call for the affected pull requests (a few cents and up to a few minutes).
  Pull requests whose first answer is fine are not affected.
- **Partly linked answers** (some probes name a claim, some do not) are left alone. Their unlinked probes keep
  their current meaning: a difference they find is shown as unclaimed.

## What it means for you

- Fewer "probe could not run on either side" results caused by a missing import.
- Fewer false "needs attention" results where the only problem was that the probe did not say which claim it
  checked.
- When the extra request happens, the record's model section shows `retried` with the reason, and
  `kept_first_answer` if the second answer did not help. Nothing needs to be changed in how you run the tool.
