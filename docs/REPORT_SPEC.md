# Reviewer report format (proposal)

Status: proposal from Jonathan, 10 Oct 2026; **adopted by Nathan on 10 Oct 2026 with the changes listed at the end** ("Adopted by Nathan"). Nathan owns the approver report in aritracodesbad123/blast-radius.

Goal: a busy approver who may not be an engineer decides in under 2 minutes from the top of page 1, and drills down only if needed.

Generator: `python -m reports.generate` (code in `reports/reviewer.py`, ported from Jonathan's `harness/report/render_report.py`, which is now a shim to it). Standard library only; PDF via headless Chrome or Chromium.

```
python3 harness/report/render_report.py <record.json> [<record.json> ...] \
  --out reports/daily/2026-10-11 \
  --claims-dir <dir with <run id>.claims.json>   # optional
  --golden-dir evals/golden                      # default
  --observations research/observations.jsonl     # default, used for golden checks
  --formats md,html,pdf                          # default
```

Output per run: `<out>/<run id>/REPORT.md`, `REPORT.html` (self-contained, inline CSS, printable A4) and `REPORT.pdf`. Output per call: `<out>/SUMMARY.md|html|pdf`, one row per run, items needing a decision first.

## Inputs

1. **Observation record** (shared schema v1, harness/schema/observation.schema.json). Required.
2. **Run directory** (the record's `logs` path, relative to `--root`): `args.json`, `junit-<side>-<n>.xml`, `class-*.txt`, `pytest-*.log`, `freeze-*.txt`, `setup.log`. Missing files show as "not available".
3. **Claims file** (optional), `<run id>.claims.json`:

```json
{
  "subject": {"kind": "pr", "title": "pandas#12345: ...",
              "pr": {"repo": "pandas-dev/pandas", "number": 12345, "url": "...", "merge_commit": "...", "base_commit": "..."}},
  "says": "one sentence: what the PR says it does",
  "says_source": "where that sentence came from (PR title/body, release note), with date checked",
  "claims": [
    {"id": "C1", "text": "...", "source": "PR body",
     "check": {"kind": "none" | "no_breaks" | "breaks_contain", "text": "substring for breaks_contain"},
     "why_not_testable": "optional, shown when kind is none",
     "explains_signatures": ["optional substrings of observed error signatures this claim accounts for"],
     "link_source": "evidence for that link (issue URL, diff)"}
  ]
}
```

The claims file only states what was claimed. The status of every claim is computed by the generator from the record and artifacts, never copied from the file.

4. **Golden case files** (evals/golden/*.json). Their assertions are re-checked against the stored records in observations.jsonl.

## Sections (in order)

| # | Section | Content | Source |
|---|---|---|---|
| 1 | Verdict banner | VERIFIED / NEEDS ATTENTION / COULD NOT VERIFY; action Approve / Approve with notes / Reject / Re-run; confidence High / Medium / Low with the reason; scope note when the run compares releases, not a PR | rules below |
| 2 | Summary in plain English | 3 bullets: what it says it does, what we observed, what to do | claims `says`, classification, verdict |
| 3 | Claims vs reality | one row per claim plus one "unmentioned change" row per observed change group | claims file + break groups |
| 4 | What changed in behavior | import failures (modules, error, lost tests) and real breaks grouped by error signature: count, affected tests (first 6, link to full list), example test with per-run outcomes, after-output (the `E` lines of the traceback, deduplicated) | class-*.txt, new-side JUnit, record |
| 5 | What went right | passed gates with their detail, runs per side, guardrails, prediction matched | record gates |
| 6 | What went wrong and how to fix it | two tables: issues in the PR or release; issues in our test environment. Each row has a concrete fix | breaks, false claims, failed gates (brlib FIXES), already-broken, flaky, network, pin override, subset, prediction mismatch |
| 7 | Trust checks | required and advisory gates, golden cases, flaky rate, network, threads, machine, a consistency check (counts recomputed from artifacts equal the record), prediction | record + artifacts + golden |
| 8 | Reviewer checklist | 5 tick boxes and a one-line decision with reviewer and date blanks | fixed |
| 9 | Reproduce | copy-paste `br_run.py` command rebuilt from args.json (non-default flags only, new `--id <id>-rerun`) | args.json |
| 10 | Appendix | PR and commits, versions, runner settings, schema hash, hand check, upstream issue, AI explanation status; timings per run; artifact links | record |
| | Glossary | 14 terms | fixed |

## Verdict rules

| Condition (checked in order) | Verdict | Action | Colour |
|---|---|---|---|
| record not accepted, or no classification | COULD NOT VERIFY | Re-run | grey |
| real_break > 0, or import_failure > 0, or any claim is false | NEEDS ATTENTION | Reject | amber banner, red action |
| flaky > 0, or an advisory gate failed, or lost_tests > 0 | VERIFIED | Approve with notes | green |
| otherwise | VERIFIED | Approve | green |

"Reject" means "do not approve as is". A reviewer can still approve an intended breaking change; the report gives them the facts.

Confidence: Low if any required gate failed. Otherwise start at High and lower one step per problem (Medium for 1 or 2, Low for 3 or more): stability below 0.99 on either side, flaky tests, failed advisory gate, no network isolation, golden cases missing or not all holding, fewer than 3 runs per side. The reason names every problem or, when High, states why.

## Claim statuses

| Status | Rule | Colour |
|---|---|---|
| proven | `no_breaks`: no real break and no import failure. `breaks_contain`: an observed signature contains the text | green |
| false | the check above fails | red |
| not testable | `check.kind` is `none` | grey |
| unmentioned change | an observed change group (break signature or import failure) that the PR description does not cover. If a claim lists it in `explains_signatures`, the row says which claim and why, but it stays "unmentioned" because the PR did not describe that effect | amber |

## Data rules

- Every number comes from the record or the run artifacts. Absent or null fields print "not available". Nothing is estimated.
- Signatures use the same normalisation as br_run.py, so report groups match `top_error_signatures_breaks` (checked in Trust checks).
- Golden checks read stored records; they are not re-run when a report is made. If the run being reported is itself a golden case, the report says the check is partly circular.

## Batch or daily summary

`SUMMARY.*` lists every run with verdict, action, confidence, subject, dependent, the one-line reason and links to HTML and PDF. Sort order: NEEDS ATTENTION + Reject, NEEDS ATTENTION + Approve with notes, COULD NOT VERIFY, VERIFIED + Approve with notes, VERIFIED + Approve. For daily ops, call the generator once with all of the day's records and `--out reports/daily/<date>`.

## Fields the report wants that the record does not have yet

Proposed schema additions (optional fields, so v1 records stay valid):

| Field | Why | Today |
|---|---|---|
| `pr` {repo, number, url, head_sha, base_sha, title} | Proof-of-Change runs a PR, not a release | comes from the claims file, or "not available" |
| `claims` (same shape as the claims file) | so the report needs one input only | separate file |
| `upstream_commit_old`, `upstream_commit_new` | exact code under test | only versions; "PyPI release wheels (no commit recorded)" |
| `per_test_outcomes` path or digest | before/after per test without re-parsing JUnit | parsed from JUnit |
| `old_output` for broken tests | "before" output; a passing test has none, so the report says so | not captured |
| `golden_check` {harness_version, passed, total, date} | golden results from a real re-run, not from stored records | stored records only |
| `explanation` (LLM) | plain-English cause with citations | status "not yet wired" |
| `reviewer_decision` {decision, reviewer, date, note} | close the loop after approval | not recorded |

## Adopted by Nathan (10 Oct 2026)

The team has one report generator: `reports/generate.py` (entry point) + `reports/reviewer.py`. The old Markdown-only
approver report was removed; `harness/report/render_report.py` is kept as a shim so the command above still works
(`--root` maps to `--runs-root`; `--golden-dir` and `--observations` are ignored, see below).

```
python -m reports.generate <record.json | observations.jsonl | eval-results.json> ... --out reports/daily/<date> \
  [--runs-root /workspace/blast-radius-research] [--claims-dir evals/fixtures/claims] [--formats md,html,pdf] [--require-v1]
```

Changes from the proposal:

1. **Evals and guardrails section** (after Trust checks): every report runs `evals.checks.evaluate_record` (shared v1
   schema with checksum check, versions, runs per side, single thread, prediction, golden case, `_safe_tags` import
   message, LLM citations) plus the report's own citation check, with How-to-fix per row. **Any eval FAIL makes the
   verdict COULD NOT VERIFY / Re-run** (new first rule in the verdict table); eval warnings give Approve with notes
   and lower confidence.
2. **Every claim cites its log line.** Each claim row and each unmentioned-change row has a "Log line" column:
   `pytest-new-N.log:<line>` plus the quoted text, linked to the file. Breaks and import failures are found by the
   longest literal fragment of their signature (pytest `E ` lines preferred); not-testable claims cite the observed
   signature they explain, otherwise the new-side pytest summary line. The report re-verifies all of them with
   `evals.checks.check_citations`; an unverified or missing citation is a FAIL in that section and lowers confidence.
   The evidence links also cite the pytest summary line of old and new run 1.
3. **Golden cases** come from `evals/golden_cases.json` checked against the stored records in
   `evals/fixtures/golden_v1.jsonl` (`--golden-records` to change) with the eval gate's own code, so the report and
   CI cannot disagree. Case names are ours (e.g. `golden-clean-sklearn151-152-imblearn`), not the file names in
   `blast-radius-research/evals/golden/`.
4. **Rerun command** uses this repo's wrapper: `BR_RUNNER=.../br_run.py python -m harness.run ...`, which forces 3
   runs per side and the single-thread env. Section renamed "Rerun command".
5. **Evidence links** is its own section (was "Artifacts" in the appendix) and adds PR and claim citations.
6. **Daily summary** gains a "Needs attention first" list above the table and an Evals column; rows link to HTML,
   PDF and MD.
7. **Inputs:** a record.json, an observations .jsonl, or an eval result .json. Claims come from `--claims-dir`
   or, new, from the record's `claims` field.
8. **Schema:** the proposed fields were added to `harness/schema/observation.schema.json` as OPTIONAL fields (rev 2,
   sha256 `088cd395...`): `pr` {repo, number, url, title, base_sha, head_sha, merge_commit}, `claims`,
   `upstream_commit_old`, `upstream_commit_new`, `per_test_outcomes`, `old_output`, `golden_check`
   {harness_version, passed, total, date, cases}, `reviewer_decision` {decision, reviewer, date, note}. `hand_check`
   and `upstream_issue` already existed. `explanation` already existed. Rev 1 records stay valid; see
   `harness/schema/README.md`. The report reads them: `pr` sets the subject and drops the release-scope note,
   `old_output` fills "Before", `golden_check` adds a "Golden cases (re-run)" trust row, `reviewer_decision`
   replaces the blank decision line.
9. **Known-answer replay rule** (Jonathan, ported 10 Oct): a failed latest replay of the golden cases
   (`research/validation/golden-status.json`, or `$BR_GOLDEN_STATUS`) forces COULD NOT VERIFY / Re-run with Low
   confidence on every report and adds a "Known-answer replay (fresh re-run)" trust row; so does a record's own
   failed `golden_check`.
