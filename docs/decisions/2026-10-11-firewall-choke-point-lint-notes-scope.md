# Firewall hardening, one gate before every model call, stricter probe lint, and text as it was at the time

## What changed

Six fixes from review:

1. The answer-key firewall now refuses a prompt bundle that has any key besides `pr`, `text` and `files`, and it
   scans nested text piece by piece.
2. A new module, `poc/model_gate.py`, is the single gate every model request must pass through.
3. The probe lint now also rejects `raise AssertionError`, classes built on `AssertionError`, and assertion helper
   calls such as `self.assertEqual(...)` or `numpy.testing.assert_allclose(...)`.
4. Benchmark mode reads a PR's description as it was when the PR was merged, when GitHub's edit history allows it.
5. The docs now say plainly that exact matching cannot catch reworded answers.
6. A new module, `poc/release_notes.py`, trims a release-notes page down to one version's own section.

Some terms used below:

- A *prompt bundle* is everything a model is about to be shown.
- The *answer key* is the file that says how each test case really turned out. It is for scoring only.
- A *model provider* is the code that sends a request to a language model.
- A *probe* is a small script that observes code on two versions so plain code can compare them.

## Why

Each fix closes a gap where information about the outcome could reach the model, or where a probe could quietly
judge instead of observe:

- A bundle key the firewall did not know about, such as `pr_text`, was skipped without being checked.
- Nothing forced the firewall to run before a model call.
- A probe could still judge with `raise AssertionError` or a unittest-style assertion.
- A PR description edited after the merge (for example, to add "this caused a regression") would hand the answer
  to the model.
- A release-notes page that covers 1.5.0, 1.5.1 and 1.5.2 contains, in its later sections, fixes for bugs that 1.5.0
  introduced. Those are exactly the answers.

## Decision

- **Refuse, don't skip.** An unknown key fails the check even when its content looks clean. A key that might carry
  text must never get past the check.
- **One gate, with no way around it.** Providers inherit from `GatedProvider`. Their real request lives in a
  private `_call` method. The only public method, `complete_json`, builds the bundle from exactly what will be sent,
  checks it, and only then calls `_call`. A provider class that tries to replace `complete_json` is rejected as
  soon as it is defined. A provider with no gate refuses everything. The gate accepts only answer-key *fingerprints*
  (one-way hashes), so generator code never opens an answer key. The model-written-probes work, which lives in
  another pull request, should make its providers inherit `GatedProvider` and rename its `complete_json` to `_call`.
- **Lint by structure.** The lint reads the probe's syntax tree, as before. It treats any call named `assertX(...)`
  or `assert_x(...)` as an assertion, and any class derived from `AssertionError` too.
- **Text as of the merge.** GitHub keeps every revision of a description. We take the last revision at or before the
  merge time. If that cannot be read (no token, or a very long history), we use the current text and record
  `current, may be edited after merge`, so a reader knows to treat it with care.
- **Trim by structure, before anything else.** Release notes are cut to the HTML section the inputs file names in
  its `notes_scope` column, for example `id=version-1-5-0`. Nested sections for other versions are removed. If the
  section is missing, trimming stops with an error instead of falling back to the whole page.

## Alternatives and tradeoffs

- *Scanning unknown keys instead of refusing them* would let odd bundles through. Refusing is stricter and may
  force callers to tidy their bundles. We accept that.
- *Wrapping providers instead of subclassing* is easier to forget. The base-class rule makes the gate part of being
  a provider.
- *Treating every `assert_` call as an assertion* also rejects harmless helpers that happen to start with that
  word. Probes can use other names.
- *Using the current description everywhere* is simpler, but it can leak outcomes. Reading the edit history needs a
  read-only token, and without one we label the text as possibly edited.
- *Relying on the firewall to strip later versions' notes* would fail on any reworded fix. Trimming by section does
  not depend on wording.
- **Exact matching cannot catch paraphrases.** That is why the trimming and the merge-time text matter more than
  the firewall.

## What it means for you

- If you build prompts, put text only under `text` and files under `files`. Anything else is refused.
- If you write a model provider, inherit from `GatedProvider` and implement `_call`. Do not call the model any
  other way.
- Probes must print observations. Assertion calls of any kind are rejected.
- Benchmark results now show `pr_text_source`, which says whether the description is the merge-time text.
- For release pairs, call `poc.release_notes.trim(html, notes_scope)` to get the notes for one version only.
