# Limitations

Cases where a check ends as could not verify. Setup limits are also written into that check's record
(`demo_helper.limitations`) in plain words, with the packages it needed and the real error.

## Current limitations

- Big applications with huge dependency lists (for example home-assistant, erpnext, or vllm-scale projects) usually end as COULD NOT VERIFY. Setup installs too much, and anything that needs a C or system build fails in Contree, because pull-request checks never install operating-system packages. Not supported: testing only the single integration a pull request touches. The operating-system package cases below are the same limit, with the error text a report shows.
- Pull requests that change only docs, comments, or docstrings end as COULD NOT VERIFY, because there is no behaviour to test.
- Contree is confirmed end-to-end only for a real product check (apprise pull request #1783) run from main in Contree-only mode (`POC_REQUIRE_CONTREE=1`), where the verdict matched the local run and nothing ran outside Contree. Not confirmed on the live Contree service: test coverage measured inside Contree, which shell runs setup, hiding of failure text, and running with a judge's own Nebius account.
- Projects that need their own package index or uv sources, or that run on a pre-release (test) build of Python, end as COULD NOT VERIFY by design. Main and the pull request must run the exact same Python version, or the result is COULD NOT VERIFY.

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
