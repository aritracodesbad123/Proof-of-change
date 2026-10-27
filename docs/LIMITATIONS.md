# Limitations

Cases where a check ends as could not verify. Setup limits are also written into that check's record
(`demo_helper.limitations`) in plain words, with the packages it needed and the real error.

## What we can and can't test

This section is for a reader who is not a programmer. It names limits the program already enforces.
The shorter copy is in the README.

### Python projects

A check is for a Python project. A project in another language is not supported. A request for a
check is accepted when the repository's language is Python, or when the project root contains a
Python project file. The tested set is these 19 small Python libraries: pytest, requests, rich,
attrs, click, isort, jsonschema, boltons, python-barcode, httpx, urllib3, python-qrcode,
itsdangerous, markupsafe, prettytable, loguru, sqlparse, toolz and invoke.

### Projects that need compiling

Not supported. A project that needs a compiler, including code written in C, C++ or Rust, is not
something these checks can build.

The daily run enforces this for dependencies before it selects pull requests. It reads the runtime
requirements on the default branch: the dependencies in the project file, and the plain lines of a
top-level requirements file. It resolves them for the Python version the checks use, and it allows
only ready-built packages. A ready-built package is already compiled, so this step compiles nothing
and installs nothing. Secret keys are not given to that step. If a requirement has no ready-built
package, every pull request of that project is left out of that run, and the reason says it needs
compiling. If the requirements cannot be resolved, the pull requests are left out for that reason
too. The check runs once per project in a run. Starting that run with `--no-wheel-check` turns the
check off.

The check does not open the project's own compiled source. It does not read optional or test
requirements, and it does not read setup.py or setup.cfg. A project can therefore still be
selected and then fail at setup. A check of one named pull request does not run this test. A study
run does not run it. When a check does reach setup and the project still needs a compiler, the
check does not install a compiler or any other operating-system package. Setup fails, and the
result is could not verify.

### Line coverage in a Contree-only run

In a Contree run, each probe is measured on the main side inside Contree. If that measurement
fails for any reason, the probe is left unmeasured and cannot count toward verified.

Measuring how much of the project's own tests ran the changed lines, inside Contree, is a separate
step. That step is built, and it is not confirmed on the live Contree service. When the report from
that step is missing, a product check stays could not verify.

### Line coverage on the main side

Line coverage of a probe is measured only on the main side, in main's line numbers. A line the
pull request adds is judged by the main lines next to it, so a check can pass without ever
running a newly added branch of the code. A pull request that only adds new files cannot be
verified.

A probe counts as measured when only some of the changed files show up in its coverage.

### Multi-line lambdas

Not supported: a changed line on a later line of a multi-line lambda is judged by the line
where the lambda is assigned. That line runs when the module is imported, so the change can be
counted as reached even if the lambda never ran.

### Plugin flags

Not supported: a project whose own test suite needs a plugin flag passed to the test run, for
example pytest's own repository needing `-p pytester`. The tool does not add per-project flags,
so these end as could not verify.

### Fresh claims and checks

The AI writes the claims and the checks fresh on every run. The same pull request on the same
code can get a different verdict on another run. An earlier run of one pull request came out
needs attention, and a later run came out verified.

### Network and keys

Tests and probes in the local sandbox have no internet. The network is turned on only while
packages are installed. Secret keys are not given to the local sandbox. They are not placed in the
shell that runs inside Contree. A behaviour that needs a network service, a password or a key
cannot be tested.

### Setup lookup

A product check needs `TAVILY_API_KEY` and refuses to start without it. A study run and the daily
study do not need it.

### What a verdict means

Verified means the behaviour the change described still holds. Needs attention means the check
found a difference a person should look at. Could not verify means the check cannot say whether
the change is fine.

Passing probes never raise the verdict. The tool never approves a pull request and never merges
one. A person decides.

### Study runs

Not built: the same-commit guard on a study run. A product check stops when main and the pull
request are the same commit, because there is nothing to compare. A study run does not apply that
guard.

### Contree on the live service

Built, and not confirmed on the live Contree service: measuring test coverage inside Contree,
which shell runs setup, hiding of failure text, and running with a person's own Nebius account.

### What 12 checks showed

Of 12 pull requests from the tested libraries, 0 were verified, 4 need attention (isort,
jsonschema, rich, prettytable) and 8 could not be verified (requests, attrs, click, urllib3,
sqlparse, toolz, markupsafe, boltons). In every record, main differed from the pull request.

The missing probe measurement in a Contree-only run, described above, alone keeps any of these
from verified. The probes crashed on main for requests, sqlparse, toolz and attrs. For attrs, the
new tests passed, but the check written for the pull request's claim crashed on main, so the claim
itself was never tested. markupsafe had a setup failure. click, urllib3 and boltons had no probe
that ran a changed line.

## Current limitations

- Big applications with huge dependency lists (for example home-assistant, erpnext, or vllm-scale projects) usually end as COULD NOT VERIFY. Setup installs too much, and anything that needs a C or system build fails in Contree, because pull-request checks never install operating-system packages. The operating-system package cases below are the same limit, with the error text a report shows.
- For apps built from many components, each listing its own requirements (like home-assistant integrations), a PR check installs only the touched component's packages plus the core requirements, read from main, and never the combined list of every component. This chooses the right packages; it is not confirmed that such a check finishes, and no such check has reached verified. If the changed files don't fall inside a single component (for example, changes to home-assistant's core files), the check ends as COULD NOT VERIFY. Confirmed on a real check: home-assistant #187420 scoped to the one integration, then setup failed building a core package that needs a C++ compiler.
- Big applications whose own core requirements need a C or C++ build, with no ready-made packages (wheels) for the Python version the project requires, end as COULD NOT VERIFY. For example, home-assistant requires Python 3.14, and two of its core packages, pymicro-vad and pyspeex-noise (home-assistant requirements.txt lines 45 and 48), have no ready-made packages for 3.14 and need a C++ compiler, which the sandbox does not have. PR checks never install operating-system packages such as compilers, and they never switch to a Python version the project does not allow.
- Docs-only pull requests are skipped in the daily run. A single check in full mode ends as COULD NOT VERIFY because the AI-probe gate needs a probe that runs a changed line. Other modes can still mark a docstring-only change VERIFIED, with the reason 'holds by construction'.
- Contree is confirmed end-to-end only for a real product check (apprise pull request #1783, confirmed on commit cecf851) run from main in Contree-only mode (`POC_REQUIRE_CONTREE=1`), where the verdict matched the local run and nothing ran outside Contree. Not confirmed on the live Contree service: test coverage measured inside Contree, which shell runs setup, hiding of failure text, and running with a judge's own Nebius account.
- Projects that need their own package index or uv sources, or that run on a pre-release (test) build of Python, end as COULD NOT VERIFY by design. Main and the pull request must run the exact same Python version, or the result is COULD NOT VERIFY.
- Product checks retry starting a Contree run after an API timeout or 5xx, only with contree-sdk 0.3.6 installed (any other version gets no retries). One narrow case remains: if Contree accepts the create request but its reply arrives after our timeout, that cannot be told apart from a lost request, so a retry can start a second run of the same step. A timeout while waiting on a run that has already started is never retried.
- The daily picker's wheel check (a dry-run resolve that skips projects needing compiling) can still let a compile-needing project through. It does not inspect the project's own C extension or its build requirements; `-r`, URL or git lines in requirements files; optional or test requirements; or `setup.py` and `setup.cfg`. Such a project is picked and can still end as COULD NOT VERIFY at setup.
- If the wheel check itself fails for a network or uv reason, every pull request of that project is skipped in that run.
- The wheel check changes which pull requests the daily run selects, so daily results from before and after it are not drawn from the same pool.
- Each product check that measures coverage inside Contree leaves one saved Contree image behind (the coverage run is kept so its report file can be read back in pieces), and that image is not deleted afterwards. Reading the report back has one overall time limit for all pieces together; if it runs out, coverage stays 'not measured' and the check stays COULD NOT VERIFY.
- A pull request that was merged by rebase, and whose recorded base already contains its head, is compared from the parent of GitHub's merge commit, which is its last rebased commit. Only that last commit is compared, not the earlier commits of the pull request. A closed pull request whose head is already inside its recorded base and that has no readable merge commit ends as COULD NOT VERIFY.

## OS packages in the local sandbox (bubblewrap)

The local sandbox gives each side its own filesystem and blocks the network outside installs. It cannot install
operating-system packages. When a check needs one, the setup lookup still finds which packages the project's own
docs name for the error, but the packages are not installed, and the result stays "could not verify".

Product checks never install operating-system packages, on any sandbox, including Contree. A project that needs a
system library, header file or build tool ends as "could not verify", and the report names the missing piece from
the error text. What is confirmed on Contree is listed under Current limitations.

What you will see in the report: "This check needs the system package(s) ..., but
this check does not install system libraries, headers or build tools. The error was: ..."
Study runs show the bubblewrap wording instead: "this sandbox (bubblewrap) cannot install OS packages".

Known cases from the 22 October batch (on the local sandbox):

| Pull request | Real error | What it needs |
|---|---|---|
| MACS3 #780, #784 | `fatal error: zlib.h: No such file or directory` | the zlib development headers |
| tornado #3787 | `Error: pg_config executable not found.` | the PostgreSQL client development files |
| optiland #962, #963 | `ImportError: libEGL.so.1: cannot open shared object file` | the EGL/OpenGL runtime for headless GUI tests |

## When no package is found

If the project's docs and its own pages name no OS package for the error, nothing is installed and the record
says so. Packages are never guessed from other sites. This applies to study runs.
