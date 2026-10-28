# Probes: check syntax with the Python that runs them, and allow one rewrite after a crash on main

## Problem
AI-written probes could crash on every main-side run, so they observed nothing:
- Probe syntax was checked by the orchestrator's own Python, which can be newer than the sandbox image's. A t-string
  passes on 3.14 and is a SyntaxError on the 3.12 image.
- A probe that built internal objects directly (for example a deprecated constructor) crashed on both sides, and
  nothing gave it a second chance.

## Decision
1. Product checks in Contree pick the image's Python from the project's own metadata (`poc/probe_python.py`).
   A version fits when it satisfies requires-python and every changed PR-side Python file parses with its grammar.
   The default image wins whenever it fits, so existing checks keep their Python and their verdicts. Otherwise the
   newest fitting classifier version is used, then the fitting version nearest the default. Available versions come
   from `POC_CONTREE_PYTHONS` (default 3.10 to 3.14). If none fits, the check is refused as not runnable here, and
   the refusal states why. The probe prompt names the chosen version, and probes that do not parse with its grammar
   are rejected (`ast.parse` with `feature_version`).
2. An AI-written probe that crashed on every main-side run gets exactly one rewrite. The model sees only the
   probe's code and its main-side error output, and the prompt asks it to use public APIs (for example pytester).
   The rewrite is frozen before its PR-side runs. In code (`cap_rewrite`), the verdict is derived again with the
   probes from before the rewrite, and the lower of the two verdicts is kept
   (needs_attention < could_not_verify / no_code_change < verified). So a rewrite can keep or lower a verdict but
   never raise it.

## Limits
`feature_version` does not catch every newer grammar form, such as the relaxed f-string quoting from 3.12. Probes
still run inside the image itself, so anything that is missed shows up as a main-side crash and gets the rewrite.
Study runs are unchanged.

## Effect on setup
When the default image does not fit, the check now starts from an image that has the right Python, instead of
installing that Python on top of the default image during setup. A project the default image already fits gets
exactly the same setup as before.

## Probe broken (fix 46)
Sometimes an observation is the same exception type, or the same skip value, on both sides, because the probe never
reached the call it was about. Two examples: a class built without its required argument raises TypeError on both
sides, and a probe that called a function that does not exist fails the same way on both. Such an observation is
now labelled not_testable and marked `probe_broken`. It is advisory only: it never counts as "does not differ"
(which used to raise attention), "no difference" or "proven". Failures that a probe records as plain text
('TypeError', 'TypeError: ...', 'SkippedDueTo...Failure', 'skipped: ...') are recognised as well as
`{"raises": ...}` and `{"skipped": ...}`. Different exceptions on the two sides are still a difference.

Re-judging 755 stored records (benchmark result sets, replayed checks and the held-out live checks), old code vs new:
- attrs #1648: needs_attention -> verified. Expected verified; the old result was a false alarm.
- sqlparse #928 (safe case): needs_attention -> verified. Expected verified.
- click #3878 (ambiguous case, not scored), one record: needs_attention -> verified. The flag came only from
  ValueError on both sides.
- connectlife-ha #742 (32 copies of one stored run): needs_attention -> could_not_verify. The flag came only from
  ModuleNotFoundError on both sides, and that run was already marked untrustworthy.
- The other 720 records are unchanged, including every boltons #586 record. No known catch is lost, and the
  known-answer suite still scores 35/35.

## Commit label (small fix)
After the self-update, the run sets POC_COMMIT to the commit that actually runs, says so when a label set
earlier named another commit, and prints `commit=<sha>` after DONE. A wrapper can read that line instead of
the value it set before the update.
