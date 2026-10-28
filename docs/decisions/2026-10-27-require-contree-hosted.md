# Hosted product routes run pull-request code only in Contree

## What changed

The GitHub App, the request-a-check worker and a hosted console now start a check with
`--sandbox-backend contree --require-contree`. A hosted console is one with `POC_HOSTED=1` set as a
server setting, or one running on Render or a Space. A single-user Codespace is never treated as hosted.

With `--require-contree`, the check selects Contree with no local fallback. If Contree cannot start,
because the Nebius key or project ID is missing or the Contree software is not installed, the check stops
before any work. It prints one line, `STOPPED: Contree unavailable: ... Result: could not verify.`, and
runs no pull-request code. A hosted console refuses the same way before it starts the check, and it
ignores the unsandboxed opt-in.

## Why

The App passed no sandbox backend, so its checks ran pull-request code in local bubblewrap. The command
line also fell back to local bubblewrap unless `POC_REQUIRE_CONTREE=1` was set. A hosted deploy runs
untrusted code for other people, so on those routes the code has to run in Contree.

## Not changed

The command-line default (`--sandbox-backend local`), a local console and the daily study are unchanged.
A Contree failure in the middle of a run already refused, with no local fallback.
