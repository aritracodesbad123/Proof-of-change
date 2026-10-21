# Console refuses to run pull-request code without a sandbox

**Date:** 2026-10-21
**Status:** accepted

## What changed

The operator console no longer starts a check with `--unsafe-no-sandbox` just because bubblewrap cannot start and Contree is not available. Bubblewrap is the local sandbox that keeps untrusted code away from the machine's files and network. Contree is a remote sandbox. `--unsafe-no-sandbox` turns that protection off.

The console now stops the check and says it will not run pull-request code. The only way to allow an unsandboxed run is to set the environment variable `POC_UNSAFE_NO_SANDBOX` to `1`. When that is set, the console still shows a warning on the health banner and on the check.

A playback of the vetted sample, which does not execute pull-request code, still runs on a host that has no sandbox.

Choosing Contree no longer also passes `--unsafe-no-sandbox`. That extra flag used to keep a local fallback alive if a remote sandbox failed. The fallback is now off unless `POC_UNSAFE_NO_SANDBOX=1` is set.

## Why

Pull-request code is untrusted. Running it without a sandbox can expose files, keys, and the network on the machine that hosts the console. An automatic fallback hid that choice. A person has to opt in on purpose, and the warning has to be visible.

## Decision

1. If Contree can start (a key, a project id, and the Contree SDK), the console uses Contree and does not disable the local sandbox gate.
2. If bubblewrap can start, the console uses it and adds no extra flag.
3. If neither can start, the console refuses. It does not launch the check.
4. `POC_UNSAFE_NO_SANDBOX=1` (also `true` or `yes`) is the only opt-in. The console then passes `--unsafe-no-sandbox` and shows a warning that names the variable.
5. The vetted sample playback, which does not run pull-request code, is unchanged.

## Alternatives and tradeoffs

Leaving the automatic fallback would keep a public demo running on hosts that cannot start bubblewrap, at the cost of executing untrusted code. Requiring Contree or bubblewrap means those hosts show a refusal instead of a result, until someone installs a sandbox or sets the opt-in. Keeping `--unsafe-no-sandbox` beside Contree would let a failed remote sandbox continue on the local machine. That path is now closed unless the opt-in is set, so a Contree failure stops the check instead of running code locally.

## What it means for you

On a machine where bubblewrap works, nothing changes. On a host where it does not, a check will not start until Contree is set up or you set `POC_UNSAFE_NO_SANDBOX=1`. If you set that variable, read the warning: pull-request code can see the machine. The prerecorded sample playback still finishes without running that code.
