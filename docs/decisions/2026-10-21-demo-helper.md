# A console check can look up setup steps and fill a missing install

## What changed

A console check and a daily check now do a short setup pass before they install the base side or the pull-request side. A study run does not. The study path is unchanged, and this pass never decides a verdict.

Before either side is installed, the check looks up the project's own install notes when a Tavily key is set. The search names that project's distribution and its GitHub address, and it stays on that repository, its docs, and its page on the Python package index. A hit that never mentions the project or that repository is dropped before it is shown, saved, or used. The same page is listed once. An old release page on the package index is folded into the current project page. Install files and the readme come before other notes, and lint or type-check settings are left out. It prints a setup plan: the Python version it noticed, any system packages, and the Python packages it will add. The same list is used on both sides. A package is added only when the project's own files already name it, or when that package's page on PyPI links back to the same GitHub repository. A Python version or a system package is used only when the sandbox can actually apply it. The local sandbox does not install system packages and does not switch Python unless that interpreter is already on the machine. A Contree sandbox can install the system packages and keeps the image's Python.

If the install, the build, the network, or the machine's memory fails, the check says "rerun, setup problem" and tries again, up to two more times. That outcome is not counted as a verdict.

If a test or a probe ends "could not verify" because something needed to run it is missing (a Python module, a system library, a fixture or data file, or a version conflict), the check reads the error, the project files, and one more lookup. It installs only what the same rules allow, on both sides, and runs that test or probe once more. Two rounds is the limit. The lookup text cannot change the result by itself. If the gap is still there, the result stays "could not verify" and the reason says "could not verify: setup gap" plus the name of what is missing.

The check also reports whether the GitHub token and, for a Nebius model, the Nebius token are present, plus free memory, free disk, and whether git, Python, and uv are installed. It does not print those token values. When the Tavily key is set, a live lookup is recorded and the console shows how many results came back, the queries, and the source links. After the report is written, a self-check compares the report with the run records and says so in plain text.

## Why

Install failures and missing test dependencies were being reported as if they were a conclusion about the pull request. A person running a demo needs to see the setup steps, and both sides of the comparison have to receive the same extra packages or the comparison is not fair. Notes from the web are useful context, but they are not a test result.

## Decision

- Keep this pass on console checks and daily checks only. A study run ignores it.
- Show the setup plan before installing either side, locally or in a Contree sandbox, and apply one plan to both sides.
- Install a Python package only when the project lists it, or when its PyPI page links back to the same GitHub repository.
- Apply a Python or system-package hint only when that sandbox allows it, and write down what was not applied.
- Retry a setup failure twice and do not count it as a verdict.
- Retry a setup-caused "could not verify" once. Leave the result as "could not verify: setup gap" plus the missing name when the gap remains. Never treat lookup text as a result.
- Record a live Tavily call when the key is set, and never write the key, the Nebius key, or a GitHub token into the log, the record, or the report.
- Check that the written report matches the records.

## Alternatives and tradeoffs

- Install whatever a web page names. That can put an unrelated package on one side and change the tests. The link-back rule and the project's own files keep the list small.
- Let the lookup text mark a pull request verified. A paragraph on the web is not a run of the tests. The rerun has to produce the new result itself.
- Keep retrying until the install works. An unbounded retry hides a real gap and can loop. Two setup retries, and one rerun of a failed test, are enough to fill an obvious hole and then stop.
- Turn the pass on for study runs. The study has to measure the same work as before. Leaving it off keeps those results comparable.

## What it means for you

On a console check or a daily check you will see setup lines before the installs: what was found, what was installed on both sides, and what the sandbox refused. Set `TAVILY_API_KEY` when you want the live lookup. Leave it unset and the check says the lookup was skipped and continues. `NEBIUS_API_KEY` is still only reported as present or missing. A study run does not print this plan and does not install from it. If a result says "rerun, setup problem", it is not a verdict. If it says "could not verify: setup gap" and a name, the check tried to fill that hole and it is still missing.
