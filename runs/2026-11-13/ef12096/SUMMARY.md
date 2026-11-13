# Proof-of-Change go/no-go: 2026-11-13 on ef12096

5 report(s) in this folder: 0 need attention, 5 could not be verified, 0 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **COULD NOT VERIFY**: python-attrs/attrs#1626: Fix inherited default method overrides (#1549). Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 2 test(s) fail on main and pass on the PR; 282 test(s) ran on main, 282 on the PR; 0 new test(s) pass, 280 unchanged
- **COULD NOT VERIFY**: mahmoud/boltons#765: Preserve bytes paths when rotating files. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 2 test(s) fail on main and pass on the PR; 15 test(s) ran on main, 15 on the PR; 0 new test(s) pass, 13 unchanged
- **COULD NOT VERIFY**: PyCQA/isort#2786: feat: remove redundant straight imports (opt-in, closes #2285). Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 75 test(s) ran on main, 75 on the PR; 0 new test(s) pass, 72 unchanged; 2 test failure(s) pre-existing and identical on both sides
- **COULD NOT VERIFY**: prettytable/prettytable#543: fix: escape LaTeX special characters in table output. Unverified behaviour claim: "No existing output changed for plain text (`& `.join structure and `\r\n` line joins untouched)."; needs a probe (3 test(s) fail on main and pass on the PR; 221 test(s) ran on main, 221 on the PR; 0 new test(s) pass, 218 unchanged)
- **COULD NOT VERIFY**: prettytable/prettytable#544: fix: escape MediaWiki markup characters in table output. Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 3 test(s) fail on main and pass on the PR; 227 test(s) ran on main, 227 on the PR; 0 new test(s) pass, 224 unchanged

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| COULD NOT VERIFY | python-attrs/attrs#1626: Fix inherited default method overrides (#1549) | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 2 test(s) fail on main and pass on the PR; 282 test(s) ran on main, 282 on the PR; 0 new test(s) pass, 280 unchanged | [PDF](attrs-1626/REPORT.pdf) |
| COULD NOT VERIFY | mahmoud/boltons#765: Preserve bytes paths when rotating files | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 2 test(s) fail on main and pass on the PR; 15 test(s) ran on main, 15 on the PR; 0 new test(s) pass, 13 unchanged | [PDF](boltons-765/REPORT.pdf) |
| COULD NOT VERIFY | PyCQA/isort#2786: feat: remove redundant straight imports (opt-in, closes #2285) | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 1 test(s) fail on main and pass on the PR; 75 test(s) ran on main, 75 on the PR; 0 new test(s) pass, 72 unchanged; 2 test failure(s) pre-existing and identical on both sides | [PDF](isort-2786/REPORT.pdf) |
| COULD NOT VERIFY | prettytable/prettytable#543: fix: escape LaTeX special characters in table output | Unverified behaviour claim: "No existing output changed for plain text (`& `.join structure and `\r\n` line joins untouched)."; needs a probe (3 test(s) fail on main and pass on the PR; 221 test(s) ran on main, 221 on the PR; 0 new test(s) pass, 218 unchanged) | [PDF](prettytable-543/REPORT.pdf) |
| COULD NOT VERIFY | prettytable/prettytable#544: fix: escape MediaWiki markup characters in table output | Not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 3 test(s) fail on main and pass on the PR; 227 test(s) ran on main, 227 on the PR; 0 new test(s) pass, 224 unchanged | [PDF](prettytable-544/REPORT.pdf) |
