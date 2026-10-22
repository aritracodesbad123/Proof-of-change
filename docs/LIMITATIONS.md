# Limitations

Cases where a check cannot finish setup in the sandbox it runs in. Each one is also written into that check's
record (`demo_helper.limitations`) in plain words, with the packages it needed and the real error.

## OS packages in the local sandbox (bubblewrap)

The local sandbox gives each side its own filesystem and blocks the network outside installs. It cannot install
operating-system packages. When a check needs one, the setup lookup still finds which packages the project's own
docs name for the error, but the packages are not installed, and the result stays "could not verify". The same
check run on Contree installs them on both sides and retries.

What you will see in the report: "This check needs the system package(s) ..., but this sandbox (bubblewrap)
cannot install OS packages. The error was: ..."

Known cases from the 22 October batch (on the local sandbox):

| Pull request | Real error | What it needs |
|---|---|---|
| MACS3 #780, #784 | `fatal error: zlib.h: No such file or directory` | the zlib development headers |
| tornado #3787 | `Error: pg_config executable not found.` | the PostgreSQL client development files |
| optiland #962, #963 | `ImportError: libEGL.so.1: cannot open shared object file` | the EGL/OpenGL runtime for headless GUI tests |

## When no package is found

If the project's docs and its own pages name no OS package for the error, nothing is installed and the record
says so. Packages are never guessed from other sites.
