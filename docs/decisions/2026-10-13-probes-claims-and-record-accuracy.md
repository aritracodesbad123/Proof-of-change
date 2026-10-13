# Probes, claims, and what a run record is allowed to say

## What changed

A *verdict* is the result of a check: verified, needs attention, or could not verify. A *probe* is a small script
that calls the changed function on the current code and on the pull request, then compares the two answers. A
*behaviour claim* is a sentence that says the old behaviour was kept.

Nine behaviours changed:

1. A resumed run keeps the first start time. The wall time in the report is the sum of each pull request's own
   time, including pull requests reused from an earlier invocation of the same folder. The report lists which
   records were reused and which invocation they came from. Each invocation keeps its own timing file.
2. A probe is *uninformative* when every input raises the same error on both sides. That probe does not count as
   having run, and it does not count as adequate coverage, even if a line counter moved. The model-free probe
   builds an input that matches the function (a graph, an array, labels, or a fitted model). If it cannot build
   that input, it does not call the function with a number or a string instead.
3. When a source file changes, the test file next to it (`<directory>/tests/test_<name>.py`) is chosen before
   other files of the same name elsewhere in the repository.
4. The claim list also matches "passed through", "left unchanged", "returned unchanged", "exactly as before" and
   "untouched". Added changelog lines and added docstring lines in the diff are scanned too. A match with no
   probe that expects the same result turns verified into could not verify.
5. A test that flips between passed and skipped on both sides, with a skip reason about memory, disk or network,
   is the machine. It is recorded as environment, not as a pull request finding. A change that only rewrites
   docstrings (the code is the same once those strings are removed) is verified, and each claim is marked
   "holds by construction". A test that passes and fails across runs is still could not verify.
6. When new tests skip because a plain installable module is missing (duckdb, ibis, sqlframe, polars, datafusion,
   pytest-asyncio), that module is installed on both sides and the tests run again. A failure that also happens
   on the base side, including the same error from the newly installed backend, is not a pull request finding.
   The verdict is could not verify. A new failure whose error is not seen on the base side is still needs attention.
7. When a pull request only adds test files, the nearest existing tests folder is run on both sides, and the new
   files are still run on the pull request side.
8. The record names the packages inside the extras that were requested, records `PYTHONHASHSEED` as `0`, labels
   the pull request's base commit separately from the main commit that was tested, always stores the head that
   was current at test time, and checks at report time whether that head has moved. The "how to fix" line agrees
   with the coverage numbers: it does not say the changed lines never ran when coverage shows they did.
9. `schema_check.log` starts with an explicit count, for example `19/19 valid`.

The shared record schema is revision 9. Every new field is optional, so older records still validate.

## Why

A resumed run was reporting only the last step's clock, so a long run looked like a couple of minutes. A probe
that raised the same exception on every input was treated as if it had exercised the change. The test next to a
changed file could lose to an alphabetical match in another folder. Sentences such as "passed through unchanged"
were missed, including when they lived in a changelog or a docstring. A skip caused by low free memory, and a
docstring-only edit, were reported as if the pull request had changed behaviour. Installing an optional module
and then seeing the same backend error on both sides was reported as needs attention, which says the pull
request caused a break. An additive test file left the base side with nothing to run. The record omitted the
packages that were actually installed, the hash seed, which main commit was tested, and whether the head moved
after the test. The suggested fix could contradict the coverage line. The schema log did not state how many
records were valid.

## Decision

- Keep the first start time, sum per-pull-request wall times, and store each invocation's timing file. List
  reused records in the report.
- Mark a same-exception probe uninformative and drop it from the "this probe ran" counts. Skip a call when the
  required graph, array or model cannot be built.
- Prefer the sibling `tests/test_<name>.py` (and `<name>_test.py`) before a repository-wide search.
- Extend the claim phrases and scan added changelog and docstring lines. A docstring-only change is verified
  and the claim holds by construction, unless the tests already need attention.
- Treat a resource pass/skip seen on both sides as environment. Keep a pass/fail disagreement as could not verify.
- Install the listed optional modules on both sides and rerun. If the new failure's exception also appears on
  the base side, record it as the backend and use could not verify when that is the only finding.
- For test files that exist only on the pull request, also run the nearest existing tests directory on both sides.
- Record the extra's packages, the hash seed, both commit ids with labels, the head at test time, and a head
  check at report time. Make the fix text follow the coverage result. Start the schema log with `N/N valid`.

## Alternatives and tradeoffs

- Counting the last step's clock is simpler and wrong for a resumed run. Summing per-pull-request times can
  overlap if two pull requests ran together; it still matches the time spent testing, which is what the report
  is for.
- Treating every identical exception as a real observation would keep marking probes adequate when they never
  called the function successfully. Dropping them means a green probe of that kind cannot support verified.
- Installing every missing import would pull in heavy stacks. The list is only modules that are a plain wheel.
- Calling a same-error backend failure needs attention would keep flagging the backend as a break. Could not
  verify says the run cannot confirm the pull request, and it does not claim the pull request caused the error.
- Hiding that failure entirely (verified) would overstate what the tests showed.

## What it means for you

The report's wall time includes earlier steps of the same folder. A line under "Reused records" names what was
kept. A probe section can say uninformative; that probe did not check the change. A claim in a changelog or a
docstring now blocks verified until a probe checks it, unless the edit is docstring-only. A memory skip on both
sides, or the same backend error after an optional install, does not become needs attention. The record names
which main commit was tested, and the report says when the head moved afterwards. `schema_check.log` opens with
the valid count.
