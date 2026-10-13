# "Verified" needs an AI-written probe that ran the changed code

## What changed

In the modes that use AI-written probes (small scripts written by the model and run on the old and new code), a
pull request is now only called **verified** if at least one AI-written probe actually ran at least one of the
changed lines. We already measure which changed lines each probe runs. If no AI-written probe touched the change,
the result is **could not verify**, and the reason says so. The earlier verdict is kept in the record.

Results that are "needs attention" or "could not verify" are not affected, and neither is the tests-only mode,
which has no AI-written probes by design.

## Why

"Verified" should mean the change itself was exercised and behaved as promised. Before, a pull request could be
called verified when the project's tests passed and the probes happened to call other code, so nothing had really
looked at the changed lines.

## Trade-offs

- More results will be "could not verify" until the probes get better at reaching changed code. That is the honest
  answer, and it shows where the probes need work.
- Probes written by the automatic, model-free generator do not count for this rule. Only AI-written ones do, as
  the rule is meant to check that the AI probe step did its job.
- The rule is written in general terms and was not tuned on any benchmark case.
