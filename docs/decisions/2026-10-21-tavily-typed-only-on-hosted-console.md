# Tavily key is typed-only on a hosted console

Date: 2026-10-21

## Context

A user check on the console could fall back to the server's `TAVILY_API_KEY` when no Tavily key was typed into the form. On a hosted console that means one visitor's check spends the operator's Tavily account, which breaks the rule that user checks never use a shared key. The Nebius key already follows that rule.

## Decision

- On a hosted console (anything that is not a Codespace or single-user console, detected the same way the sign-in code does: `CODESPACES` or `POC_SINGLE_USER`), the check's environment gets only the Tavily key typed into that session. The server's `TAVILY_API_KEY` is removed from the child environment and kept only so its value is redacted from logs and replies.
- With no typed key, the related-reports lookup is skipped with its usual log line.
- In a Codespace or single-user console, the `TAVILY_API_KEY` secret still works as a fallback, since it belongs to the person running that Codespace.

## Consequences

Hosted visitors who want related bug reports must type their own Tavily key. Tests cover the hosted case with and without a typed key and the Codespace fallback.
