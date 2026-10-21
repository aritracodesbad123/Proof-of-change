# A test that fails only on the pull request is not ignored

## What changed

A test that passes on every run of the current code, and passes on some runs of the pull request but fails on others, used to be called flaky and then ignored. The pull request could still come out verified. That test is now a possible regression. When the base always passed, the pull request sometimes fails, and a pull-request result repeats, the verdict is needs attention. When the pull-request runs are so mixed that no result repeats, the verdict is could not verify. It is never verified.

A test that is flaky on both sides is still only listed. It does not decide the verdict. The same split applies to a probe observation.

The setup rerun is the only step that can raise could not verify to verified. Before it does, probe line coverage is measured again, but only when the change is small (200 changed lines or fewer). A larger change skips that measurement, and the rerun then cannot raise the verdict to verified.

A web search can suggest package names. Those names are installed only when the package's page on the Python package index links back to the same repository. The package author writes that link. It stops an accident. It does not stop someone who is trying to get a bad package installed.

A probe result that stays the same on the base and is too mixed to name on the pull request is labelled unstable on the pull request. It is not labelled flaky, so later checks do not drop it as noise. The report lists tests that are unstable only on the pull request on their own line.

A measurement that finds no changed lines is not adequate. A setup rerun cannot become verified from that measurement. The same rule already applies when judging whether a probe reached the change.

## Why

Ignoring a failure that shows up only on the pull request treats a possible break as noise. A setup rerun that reports success without measuring probe coverage again can call a change verified when the probes never ran the changed lines. The package-index link is written by the package author, so it is a guard against a mistake, not against an attack.

## Decision

- Count a result that is stable on the base and unstable only on the pull request as a possible regression. Needs attention when it can be called. Could not verify when it is too mixed to call. Never verified.
- Keep today's handling when a result is flaky on both sides.
- Recompute probe line coverage after a setup rerun, and only then allow could not verify to become verified. Skip that measurement when the change is larger than 200 lines, and do not raise the verdict in that case.
- Say plainly that a suggested package is installed only when its package-index page links back to the same repository, and that this stops accidents, not a determined attacker.
- Label a probe result that is stable on the base and too mixed to call on the pull request as unstable on the pull request, not as flaky.
- Treat a measurement with no changed lines as not adequate, so a setup rerun cannot become verified from it.

## Alternatives and tradeoffs

- Keep calling every one-sided wobble flaky. That misses a break that does not fail on every pull-request run.
- Always call the wobble needs attention, even when every pull-request run is different. That overstates a result we cannot name. Could not verify is the honest verdict there.
- Measure probe coverage again after every rerun, including a large change. That can be a long extra run. Skipping it on a large change means those reruns stay could not verify.
- Treat the package-index link as proof the package is safe. The author of the package writes the link, so a determined attacker can write one too.

## What it means for you

A pull request whose tests pass on the current code and fail on only some runs of the change will no longer come out verified. If the runs are too mixed to name the failure, the verdict is could not verify. A test that wobbles on both sides is still listed and still does not decide. After a setup rerun, a small change is measured again before it can be verified. A larger change is not measured again, and it stays could not verify. A measurement with no changed lines is not adequate, so that rerun stays could not verify too. A probe result that is too mixed to call on the pull request is labelled unstable on the pull request, and the report lists those tests on their own line. A suggested package is still installed only when its package-index page links back to the repository, and that check is not a defence against someone trying to get past it.
