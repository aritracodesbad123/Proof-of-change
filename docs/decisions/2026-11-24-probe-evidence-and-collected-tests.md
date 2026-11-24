# Probe evidence and collected test files

## What changed

Four checks got tighter about what may count as proof, and one stop that was holding a proved claim back was removed.

An agreeing probe result stays a note. It still does not, by itself, verify a pull request. It no longer pulls a claim back down to could not verify when a different observation of that same claim already showed the two sides differing, the way the claim said they would. A probe whose changed-line count was never taken can still be the probe that exercised the change, but only when it recorded that kind of difference and the tests ran every changed line. A count that was taken and came out zero still does not count.

A probe is compiled before it is kept, not only parsed. Parsing accepts a `nonlocal` written at the top of the file. Compiling rejects it, which is what happens when the probe actually runs. A probe that fails this check is sent back once through the regenerate that already existed. A daily run also sends a probe that crashed on every base-side run back once, the same single rewrite a product check already used. A study run does not.

A probe that defines its own class or function when importing the real target fails is rejected. So is a probe that defines a class or function using a name it should have imported from the project. The existing name check reports that, and the existing one regenerate applies. Separately, when one observation from a call is the same exception or skip on both sides, every other observation from that same call that also came out the same is marked broken. Those values are not evidence. A field that differs is a real result and is kept. A different call is left alone.

The rule that says the tests already prove a change now accepts a test file the run actually collected. The file does not have to be named `test_*.py` or `*_test.py`. Collection is read from the junit ids and from the stored list of collected files. A test id that both sides already had does not count. The separate cross-run settlement set is unchanged: it still uses only default-named edited test files.

## Why

An agreeing result on one input was being treated as the thing that verified the pull request, even when another input of the same claim had already shown the difference and the tests had failed on the base and passed on the pull request. That held proved claims at could not verify.

A probe with `nonlocal` at the top of the file parses and then crashes in every run. The crash was not sent back on a daily run, so the same broken probe was kept.

A probe that could not import the real classes defined its own stand-ins and then recorded values from those stand-ins. One field was the exception, correctly ignored. A sibling field was `None` on both sides and was scored as "does not differ", which raised needs attention. The probe had tested itself.

A project whose tests live in a file pytest collected, but which is not named `test_*.py`, never counted as the tests proving the change.

## Decision

Keep the agreeing result advisory. Do not demote a claim that another observation has already proved. Do not verify a claim that has no such observation and is not settled by the cross-run.

Compile every probe with `compile(src, name, 'exec')`. Rejected probes use the existing regenerate. Crashed probes on a daily run use the existing one rewrite.

Reject stand-in definitions in the existing name check. Mark every observation from a broken call broken.

Let the tests-prove rule read the files the run collected. Do not widen the cross-run settlement set.

Nothing here rewrites a saved record. Nothing here calls a model during a replay.

## Alternatives and tradeoffs

Treating every agreeing result as proof would have verified claims the probe never showed. Leaving the demotion in place kept proved claims at could not verify.

Counting a measured zero changed lines as a hit would have verified a probe that was shown not to reach the change. Only a missing count, together with a claimed difference and tests that ran every changed line, is accepted.

Sending a crashed probe back more than once would spend another model call. The daily run uses the one rewrite that already existed.

Guessing that any changed `.py` file is a test, without a junit id that resolves to it, would have treated library code as a passing test. The id has to resolve to a file the pull request changed, or to a file the run recorded as collected.

## What it means for you

A probe that agrees with itself on an input the tests have already shown is a change stays a note. If another observation of that claim already showed the difference, the note does not block a verified result. If nothing else showed it, the note still does not verify the pull request.

A probe that does not compile is sent back once. A daily run does the same for a probe that crashed on every base-side run.

A probe that defines a fake class when the import fails is not run. Values from a call that raised the same exception on both sides are not used as evidence.

A test file pytest collected counts for the tests-prove note even when its name is not `test_*.py`.
