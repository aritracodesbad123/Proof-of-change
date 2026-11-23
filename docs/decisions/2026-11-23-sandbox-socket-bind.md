# Local servers bind inside each test run

## What changed

A test run that does not share the host network now gets a private network namespace with the loopback
interface brought up, and with `localhost` mapped to that interface. The command that brings loopback up
drops the extra capability before the project's own command runs. Installs and builds still share the host
network, because that is when packages are downloaded.

A failure whose error is a bind problem (failed to bind, address already in use, could not assign a local
address), a local name that does not resolve, or the same setup or teardown error, and that same error
also happens on the base side, is recorded as the environment. It is not a new failure and it does not, by
itself, produce needs attention. When every remaining failure is of that kind, the verdict is could not
verify, at low confidence, and the reason names the error in plain words. It is not "Reject" and it is not
high confidence.

An assertion that only happens on the pull request is unchanged. A bind error that does not happen on the
base is unchanged. A run that was going to be verified is not made verified by ignoring a real failure, and
a docstring-only result does not turn one of these environment failures into verified.

Nothing in this rule names a project or a package, and there is no table from an error text onto a package.

## Why

Servers that the tests start themselves, on `127.0.0.1` or `localhost`, were failing inside the sandbox.
The private namespace was already there, and on current bubblewrap the loopback interface is up, but
`localhost` did not resolve: the sandbox does not mount the host resolver when the network is off. The
client retried and raised `OSError: failed to bind socket`. Those failures were counted as new failures on
the pull-request side. One run reported 1,084 new failures, all of them that bind error, while the same
tests outside the sandbox had no new failures. The same shape of false alarm had already happened on
earlier runs.

## Decision

- Keep one private network namespace per sandboxed command that does not ask for the network. Bring
  loopback up, then drop capabilities, and mount a hosts file that maps `localhost` to `127.0.0.1` and to
  `::1`. Do not mount the host resolver.
- Treat an environment error as shared when the same signature appears on the base side. A saved record
  that kept the exception type, and not every message, uses that type. When every message the record did
  keep is that one error, the failures whose text was not stored are the same error.
- Report could not verify, naming the error, when nothing else is wrong. Do not report verified.

## Alternatives and tradeoffs

- Sharing the host network for tests would make `localhost` resolve, and it would also let every run fight
  over the same ports and reach the network. The private namespace stays.
- Ignoring every setup failure would hide a setup assertion that only the pull request raises. An
  assertion is still a finding. Only the same environment error on both sides is set aside.
- Matching only the full message text would leave older saved records unchanged, because those records
  keep the base exception type and the first messages, not every line. The exception type is used for
  those records. A live run still compares the messages themselves.

## What it means for you

A test that starts a server on localhost can bind inside its own run. A bind or setup error that already
happens on the base is described as the environment, with low confidence, instead of as a reason to reject
the change. A real failure that only the pull request shows is still reported.
