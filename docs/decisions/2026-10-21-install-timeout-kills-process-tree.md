# An install that runs out of time is stopped with its whole process tree

## What changed

When an install passes its time limit, the runner stops that install and every process it started. That includes a child that left the process group by calling `setsid` (a call that starts a new session, so a signal sent to the original process group does not reach it).

The install is recorded as timed out. The text is `install timed out after {timeout}s (whole process tree killed); see {log}`, where `{timeout}` is the limit in seconds and `{log}` is the log file name. It used to be recorded as `install failed (timeout)`.

## Why

A time limit that only signals the process group leaves a `setsid` child running. The install then looks like an ordinary failure, so a later reader cannot tell a hang from a broken install.

## Decision

- On a timeout, `install_side` returns the timed-out text above and does not call it an install failure.
- `run` stops the whole process tree. It freezes the tree first, so nothing forks or is reparented while the list is collected, then it kills every member. A process-group kill remains as a backstop for anything still in the original group.

## Alternatives and tradeoffs

Killing only the process group is simpler, and it misses processes that started their own session. Waiting for those children would hold the machine until they exit on their own. Freezing the tree before killing it closes the gap where a child forks while the list of processes is being collected.

## What it means for you

A hung install ends at the time limit, and its children do not keep running. The log and the failure text say the install timed out. Verdicts, guards, and scores are unchanged.
