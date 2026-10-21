# Tavily runs on a check a person asks for, when a key is set

**Date:** 2026-10-21
**Status:** accepted

## What changed

The setup lookup is built. It finds missing-package and setup sources from the project's own files and from PyPI. A package named by that lookup is installed only when the PyPI page links back to the GitHub repository. The lookup does not choose packages by itself. It runs only when `TAVILY_API_KEY` is set. When the variable is missing, the lookup is skipped and the check continues.

A requested check reads that variable from the worker's environment. If it is missing, the worker logs a line that names the variable and does not print a key. The check still starts, with the advisory swarm on.

A Codespace asks the judge for the same variable as a recommended secret, also named `TAVILY_API_KEY`. The judge types their own key. Tavily keys are free. This project does not ship or share one. The console has a hidden field next to the Nebius key for the same value. A pasted value stays in the server's memory for that sign-in and is copied only into the check's environment. It is not written to disk, logs, reports, or replies. Without the key, the lookup is skipped and the check continues.

Study runs and benchmark runs still leave the advisory swarm off unless they ask. The request-a-check daily cap stays 5.

## Why

Judges who request a check, or who open a Codespace, should get the same setup lookup the helper already runs on a console or daily check. A missing key must be obvious, and the key itself must never be stored in the repository or shown in a comment.

## Decision

1. The worker reads `TAVILY_API_KEY` from its environment, passes it to the check, and logs a fixed skip line when it is empty.
2. The Codespace dev container recommends that secret. The console password field stores a pasted value in memory only.
3. The requirements text matches the helper: project files and PyPI, with a GitHub link-back check. It does not describe a search for related bug reports.
4. The advisory swarm stays on for a requested check and for the Codespace console. Study and benchmark defaults stay off.

## Alternatives and tradeoffs

Skipping the lookup whenever the key is missing keeps a check runnable on a machine that has no Tavily account. Requiring the key would stop those checks. Putting the key in the repository would expose it. Setting it for every process in the Codespace is unnecessary: the recommended secret and the console field are enough for a check.

## What it means for you

On the project machine, set `TAVILY_API_KEY` in the worker's environment if you want the lookup. If you do not, the log says the lookup was skipped. In a Codespace, type your own key into the recommended secret, or paste it into the hidden field. Keys are free at https://app.tavily.com/. Without the key, the lookup is skipped and the check still runs. Do not commit a key.
