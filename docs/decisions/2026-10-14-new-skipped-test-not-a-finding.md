# A new test that is skipped is not a problem with the change

## What changed

If a pull request adds a test that did not exist before, and that test is skipped when it runs, we now list it as
"new test skipped" in the report. It no longer makes the result "needs attention".

A test that existed before and now skips still counts as a change, and a new test that skips because an optional
package is missing still makes the result "could not verify", as before.

## Why

On 14 Oct a numpy pull request was marked "needs attention" only because four new test variants for complex numbers
skip themselves ("complex input cannot be cast to a real dtype"). They never ran before, so nothing that worked
before stopped working. It was a false alarm.

## Trade-offs

- If a pull request adds a test that always skips, that test checks nothing, and we no longer point that out as a
  problem. It is still listed in the report, and the coverage rule still requires the changed lines to be run.
