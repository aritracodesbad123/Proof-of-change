# Human review: PostHog/posthog#120637 ("fix(aio): warn only on slow thread waits in on_asyncify_pool")

Order followed as far as the check got: the fixed test suite could not start because installing the project failed, so no AI probe was drafted and the review pause never opened (`operator_approval: off` although review was requested).

- **Automatic run:** `install failed (1)`. PostHog's `pyproject.toml` requires exactly Python 3.14.7 and the check created the test environment with Python 3.12.
- **Review run:** `install failed (2)`. This time the setup helper switched to a local Python 3.14 interpreter, but that interpreter was not visible inside the sandbox ("No interpreter found at path ..."), so the install failed again.

Kept: nothing. Dropped: nothing. Added: nothing. There was no draft to review, and adding test ideas would not help while the project cannot be installed.

**This is a setup failure, not a verdict about the PR.** Neither run counts as a verdict. Reviewer test ideas for a future run, once install works: (1) `on_asyncify_pool`: a slow execution with a fast thread wait logs no `asyncify_slow` warning (the PR's change); (2) `on_asyncify_pool`: a slow thread wait still logs exactly one warning; (3) `asyncify`: a slow execution still logs a warning (unchanged); (4) outside a Temporal activity nothing is logged, and the wrapped function's return value and exceptions are unchanged.
