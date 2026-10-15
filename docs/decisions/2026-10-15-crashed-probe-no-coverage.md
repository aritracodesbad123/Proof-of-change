# A crashed probe no longer counts as having run the change

## What changed

An AI-written probe now counts toward changed-line coverage, and can be "adequate", only if it produced usable
output on the main side. A probe is treated as crashed when every main-side run ended in an error: an exception,
output that is not the expected JSON, a timeout or a non-zero exit. A crashed probe, or one with no observations,
is marked not adequate and its changed-line count is set to 0 (the lines it touched before failing are kept in
the record as `changed_lines_touched`). The rule that verified needs an AI-written probe that ran a changed line
ignores such probes. Probes rejected before running were already never counted.

The coverage gate now also ignores probes marked "uninformative" and "not_run", not only crashed or empty ones,
and this can lower verdicts too. That is intended, for the same reason: a probe that didn't really exercise the
change can't support "verified".

A probe that works on main but crashes on the PR side is not treated as crashed: that difference is a finding,
and its red or amber results still count.

## Why

A probe that crashes after importing the changed module can touch changed lines without observing anything.
Counting those lines let a run come out verified on the strength of a probe that produced nothing, while a run of
the same PR whose probe ran cleanly but missed the change came out could not verify. The verdict then depended on
how the generated code happened to fail.

## Trade-offs

More pull requests come out could not verify when the model writes a probe that crashes, including some where the
tests alone exercise every changed line. That is intended: under the AI-probe gate, verified needs a probe that
actually observed the change. Retrying a crashed probe is a separate change.

One known case: a pull request whose only AI-written probe crashes now comes out could not verify even when its
tests pass and run every changed line, because verified needs an AI-written probe that ran the change. In the
15 Oct check, skrub#2323 drops from verified to could not verify for exactly this reason. This is intended: a
wrong "verified" costs more than an honest "could not verify". An earlier finish line expected skrub#2323 to stay
verified on its tests alone, and that finish line was dropped on purpose: the team chose to keep the rule that
verified needs an AI probe that really ran the change. That way a later reader knows the gate didn't drift. A
variant that allows verified on the tests alone will be measured separately behind a switch and is not going into
main.
