# Edited patterns get probes on inputs just past the old match boundary

Date: 2026-10-29

## Decision

Product checks only (`poc/boundary_probes.py`, called from `model_probes.generate`):

- **Trigger.** The rule fires only when the PR diff edits an existing pattern in a source file: a removed line and
  an added line of the same hunk each hold a pattern literal, and the two are similar enough to be one pattern
  edited. A brand-new pattern never fires, and neither do test files, non-Python files or a pattern that is only
  re-wrapped.
- **Prompt.** When it fires, the probes prompt gets one more paragraph. It names the pattern by its base-side file,
  line and old text only, and asks for at least one probe on inputs just past the old match boundary: the match
  followed by a space, by other text, by a newline with text after it (`"<Widget>\nnext"`; a bare trailing newline
  tests nothing, because `$` also matches before it), and preceded by text. The base side is the reference.
- **Exclusion.** The paragraph suggests only claims that are testable, expect "same", and do not just re-run the PR's
  own test: a test-outcome sentence, or one naming a test function the diff adds.
- **No auto-linking.** The paragraph only suggests claim ids; the model links probes to claims itself.
- **Record.** The edited patterns are recorded under `probe_plan.model_boundary_rule`.
- **Deferred.** Seeding claims from "preserving existing behaviour" in the PR text (option B) is left for later.

## Why

A PR that tightens an existing pattern can fix its own example and stop matching ordinary text. Its test, and an
"adjacent tags are now split" claim, are both confirmed on the PR, so neither catches the loss. In a saved check of
an edited tag pattern, the one probe that caught it used an expect-same claim on `"<a>content</a> "`: the base
side kept four tag spans and the PR side kept none in all 3 runs, which was judged false_claim and needs attention.
This rule asks for that kind of input every time an existing pattern is edited.

## Evidence (offline)

- Fires on the saved diff that edits the tag pattern (line 85 of the highlighter module). Stays silent on the saved
  diff that adds a new keyword pattern with a lookahead.
- A fixture is copied unchanged from the saved catch. Judged again from its runs, the trailing-space observation is
  false_claim (red) and the plain tag is proven.
- Mutations: each rule broken in turn makes a test fail. These covered the trigger (a new pattern fires, any
  similarity counts, test files counted), the prompt (boundary wording or the newline-with-text form removed), the
  exclusion (test re-runs allowed, test names ignored) and the wiring (the rule added to study runs).
- The rule changes only the prompt, so judging and verdicts on saved records are unchanged. A re-score of the 72
  saved records with `final()` gives the same counts as main.

## Risks

- **Base side only.** The trigger reads the diff, so the model learns that a pattern was edited, but only base-side
  text reaches the prompt. That is close to the changed-path list the freeze rule already allows.
- **Not shown live.** Whether a live model writes the right inputs is not yet shown: one saved catch, no live run.
- **Noise.** More probe inputs may raise the false-alarm rate. That should be measured before any wider use.
- **Pattern detection is lexical.** A raw string or a string passed to a re function that holds regex tokens counts
  as a pattern. Patterns built in other ways are missed.
