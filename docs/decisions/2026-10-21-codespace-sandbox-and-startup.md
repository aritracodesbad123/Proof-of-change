# Codespace setup, console start, and the sandbox

## What changed

A live test in a fresh Codespace found three problems. The console did not stay running after the start command. The console web page was not built. Bubblewrap could not create a user namespace, so the console refused to run pull-request code.

- Setup now runs from `.devcontainer/post-create.sh`. It stops at the first failing step, logs to `/tmp/poc-setup.log`, checks that the web page was built, and reports whether the sandbox can start.
- `start-console.sh` builds the web page if it is missing, starts the server detached from the start command, waits up to 30 seconds for port 8787 to listen, and prints a clear result. The private-port refusal is unchanged.
- The container runs with `--security-opt seccomp=unconfined` and `--security-opt apparmor=unconfined`. It is not privileged and gets no added capabilities.

## Why

Docker's default seccomp profile blocks creating user namespaces without CAP_SYS_ADMIN, and the host AppArmor policy can block it as well. Relaxing these two filters is the smallest change that may let bubblewrap start. Privileged mode and SYS_ADMIN give far more than bubblewrap needs.

The Codespace is the judge's own short-lived machine and holds none of the project's secrets. Pull-request code still runs inside bubblewrap, with an allowlisted environment that never carries the model or lookup keys.

## Decision

- Relax seccomp first, then AppArmor. Do not use privileged mode. Add SYS_ADMIN only if a retest shows both are not enough.
- This change has not been tested inside a Codespace. A retest in a fresh Codespace decides whether more is needed: `bwrap --ro-bind / / true && echo SANDBOX_OK`.
- The README says plainly that live checks in a Codespace are not confirmed yet and points to the results page and request-a-check.
