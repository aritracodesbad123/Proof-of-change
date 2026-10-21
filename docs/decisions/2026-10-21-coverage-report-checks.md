# Coverage reports must cover every changed file

Date: 2026-10-21

## Decision

`poc/coverage_gate.measure` now returns "not measured", with a plain reason, when:

- the report has no `files` mapping, an empty one, or is not valid JSON;
- an entry is badly shaped (line lists that are not lists of integers);
- any changed Python file is missing from the report.

Before, a report that left out the changed file counted as "measured, 0 of 0 lines", so a product check
could come out verified with no real coverage. A Contree error or timeout during the coverage run is also
caught and recorded as "not measured", so the check keeps its cap instead of crashing. Only lines the PR
changed are counted; lines that ran elsewhere in the file never count as covered.

Probe adequacy keeps its old per-file reading (a probe need not import every changed file), but an empty
or badly shaped report is still "not measured" there.

## Known limitation L2: forged coverage reports

The coverage report is written by a process running the PR's own code. PR code could still write a
forged report that lists every changed file and claims every line ran, and the gate would accept it. The
local sandbox path has the same gap. Closing it needs the report to be produced or checked outside the
PR's reach (for example, coverage data collected by a process the PR code cannot write to).
