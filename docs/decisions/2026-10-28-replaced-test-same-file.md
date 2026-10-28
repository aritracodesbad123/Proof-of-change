# A removed test counts as replaced only inside the same test file

A test the pull request removes used to need attention every time, even when the pull request rewrote it in a test file it edits (rich #4143). Now a removed test is treated as replaced, and is not a finding, only when all of these hold:

- the removed test lives in a test file the pull request edits, matched by full relative path (the test id's module path must equal the file's path or be a whole-folder suffix of it). Only test files count (`test_*.py` or `*_test.py`). A same-named file in another folder does not match, and a bare id that fits two edited files matches neither;
- that same file gains at least as many new passing tests as it lost. New tests in any other file do not count;
- nothing regresses, newly fails or turns unstable on the pull request;
- at least one test ran on both sides with the same result (skipped on both does not count), so an empty run cannot clear a removal.

A replaced test never makes a pull request verified: the old test did not run against the new code, so the result is could not verify, with the reason given. Any other removed test still needs attention.

The comparison now also lists the ids of new passing tests (`new_tests_passing_ids`) so the same-file count can be made.
