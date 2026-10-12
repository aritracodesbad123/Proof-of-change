"""A pull request's description as it was when the PR was merged.

A PR description can be edited at any time, including after the merge, for example to add "this caused issue
#1234". For benchmark cases that would leak the outcome into the generator's input, so benchmark mode uses the text
as it stood at merge time when GitHub's edit history allows it.

GitHub keeps each revision of a description (GraphQL `userContentEdits`: one node per revision, newest first, the
first revision dated at creation; `diff` holds the full text of that revision). `body_at_merge` chooses the last
revision at or before `mergedAt`. Sources recorded in the result (`pr_text_source`):

    "at merge: never edited"                         no revisions: the current text is the original text
    "at merge: edit history (revision of <time>)"    the revision in force at merge time
    "current, may be edited after merge"             no token, no history, or the history is incomplete

The GraphQL request needs a token (GITHUB_TOKEN, read-only); it is a query, it changes nothing.
"""
from __future__ import annotations

import json
import os
import urllib.request

CURRENT = "current, may be edited after merge"
QUERY = """query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) { pullRequest(number: $number) {
    body mergedAt createdAt lastEditedAt
    userContentEdits(first: 100) { totalCount nodes { editedAt deletedAt diff } } } } }"""


def body_at_merge(pr: dict) -> tuple[str, str]:
    """pr: the GraphQL pullRequest object. Returns (body, source)."""
    body = pr.get("body") or ""
    merged = pr.get("mergedAt")
    edits = pr.get("userContentEdits") or {}
    nodes = [n for n in edits.get("nodes") or [] if n and n.get("diff") is not None and not n.get("deletedAt")]
    total = edits.get("totalCount") or 0
    if not merged:
        return body, CURRENT + " (PR not merged)"
    if total == 0 and not pr.get("lastEditedAt"):
        return body, "at merge: never edited"
    before = sorted((n for n in nodes if n.get("editedAt") and n["editedAt"] <= merged), key=lambda n: n["editedAt"])
    if before:
        if total > len(edits.get("nodes") or []) and not any(n["editedAt"] > merged for n in nodes):
            return body, CURRENT + " (edit history too long to read fully)"
        last = before[-1]
        return last["diff"], f"at merge: edit history (revision of {last['editedAt']})"
    return body, CURRENT


def fetch(repo: str, number: int, token: str | None = None, timeout: int = 60) -> dict:
    """The GraphQL pullRequest object (read-only query)."""
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("no GITHUB_TOKEN: GitHub's GraphQL API needs a token to read edit history")
    owner, name = repo.split("/", 1)
    data = json.dumps({"query": QUERY, "variables": {"owner": owner, "name": name, "number": int(number)}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=data,  # br-allow-external: read-only GraphQL query
                                 headers={"Authorization": f"Bearer {token}", "User-Agent": "proof-of-change-ops",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    if d.get("errors"):
        raise RuntimeError(f"GraphQL error: {d['errors'][0].get('message')}")
    return d["data"]["repository"]["pullRequest"]


def description_at_merge(repo: str, number: int, current_body: str, token: str | None = None) -> tuple[str, str]:
    """(body, source); falls back to current_body with source CURRENT when the history cannot be read."""
    try:
        return body_at_merge(fetch(repo, number, token))
    except Exception as e:  # noqa: BLE001
        return current_body, f"{CURRENT} (edit history unavailable: {type(e).__name__})"
