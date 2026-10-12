# Probes

One file per PR: `probes/<owner>/<repo>/<pr>.py` (several: `<pr>-<name>.py`). Each is a small deterministic Python
script run on both sides of the PR (main and PR) in the same environments as the tests. It begins with a literal
`PROBE` dict and prints `{"observations": {...}}` as its last line.

```python
PROBE = {
    "id": "short-name",
    "target": "owner/repo#123",
    "about": "what behaviour this checks",
    "timeout_s": 120,
    "claims": [  # what the PR says; observations not covered by a claim must not change
        {"id": "C1", "source": "PR description", "text": "...", "covers": ["obs.name.*"], "expect": "differs"},
    ],
}
```

Rules: fixed seeds, no network, no files outside a temporary directory, JSON-only values (lists, not tuples; string
keys). An observation that differs between main and the PR and that no claim covers, a claim the observations
contradict, or an observation that varies between runs makes the verdict needs_attention. See
`docs/OPERATIONS.md` (section "Probes") for the full label table.

**Provenance (freeze rule, `poc/freeze.py`).** Add `"provenance": "pre-registered"` only to a probe written from the
PR title, description and base-side code BEFORE any result of the PR was known. Anything else (including every probe
written after looking at a run) is `"provenance": "post-hoc"`, which is also the default when the field is missing.
Fixed probes are never blind: they are known-answer regression cases and are excluded from blind-eval scoring
(records label them `fixed (post-hoc, written after results were known)` or `fixed (hand-written)`).
