# A runner config-file path is not a pull-request verdict

## What changed

Preparing a sandbox drops two runner settings, `PIP_CONFIG_FILE` and `UV_CONFIG_FILE`, when their value is a path on the machine that started the run. The empty-file sentinel (`/dev/null`) is kept. A product install still sets `PIP_CONFIG_FILE` to that sentinel and `UV_NO_CONFIG=1`, so pip and uv do not read a config file. The sentinel is allowed through the install allowlist check that runs before a heavy build. The path itself is never copied into the environment of the sandbox subprocess.

A setting that is not remedied this way still raises `UnsafeEnv`. The setup retry does not catch that exception and store it as an install result. The refusal stops the run. It is written as a run-level infrastructure failure on the go/no-go summary. It does not write a per-pull-request `could_not_verify` record, and a placeholder record left because the check had started is removed. Authentication variables, proxy settings, and TLS trust settings (for example `SSL_CERT_FILE`) are not in the dropped set. Other infrastructure failures, such as the compiler running out of memory, are unchanged.

## Why

A product check installs the checkout with a heavy-build step. That step checks the environment it is about to give the sandbox subprocess. The product install had put `PIP_CONFIG_FILE=/dev/null` in that environment so the runner's pip config could not choose a package index. The name was not on the allowlist, so the check raised `UnsafeEnv` and named `PIP_CONFIG_FILE`. The harness stored that exception as `could_not_verify` on the pull request. The refusal is about the runner's environment, not about the change under test.

The runner's own value is a local path. That path must not be handed to the sandbox subprocess or sent out to another service. Replacing it with the empty-file sentinel is the existing product-install rule. Treating the sentinel as a new secret was what stopped the check.

## Decision

- Drop `PIP_CONFIG_FILE` and `UV_CONFIG_FILE` when the value is anything other than the empty-file sentinel, at the moment the sandbox environment is built and again in the dict passed to the subprocess.
- Treat the sentinel as a remedied install setting. It is not a credential and it is not a runner path.
- Leave every other `UnsafeEnv` (a credential-like name, a URL that contains a password, or a name that is not allowlisted and not remedied) as a hard refusal. Surface it as one run-level infrastructure line and a no-go summary. Do not store it as a verdict about the pull request.
- Do not drop authentication variables, proxy settings, or TLS trust settings, and do not turn other infrastructure failures into silence.

## Alternatives and tradeoffs

Putting `PIP_CONFIG_FILE` on the allowlist with any value would let a runner path into the sandbox. Stripping every unfamiliar variable would also remove proxy and certificate settings the sandbox is allowed to keep, and would hide real secret refusals. Recording the refusal as `could_not_verify` on the pull request keeps a PDF, but it reads as evidence about the change. The run-level no-go summary already exists for a run that cannot start; this refusal belongs there.

## What it means for you

A product check whose runner has `PIP_CONFIG_FILE` set can install and test. The sandbox sees `/dev/null`, not the runner's file. If the environment still contains a real secret, the run stops with a no-go summary that says the sandbox was refused and that this is not a result about the pull request. The summary does not contain the secret or the config-file path.
