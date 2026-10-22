# Product checks stop early on installs they cannot finish, and a missing import keeps its real error

**Date:** 2026-10-22
**Status:** accepted
Merged as 0886b27, approved by George and Jonathan.

## What changed

A product check (a check started with `--product-check`) now stops before it spends retries on three kinds of install, and a could-not-verify result caused by a missing import or a missing library keeps the real pytest error.

- If the project requires a CUDA build (a required dependency named `nvidia-*-cu*`, a `cuda-*` package, or a `+cu` wheel), the check does not install it. The reason says the project needs a GPU / CUDA build and names that requirement. A required package whose name only contains `nvidia`, and an optional extra that mentions CUDA, do not stop the check.
- If the install log says the disk is full (`No space left on device`, and the same kind of message), the check does not retry. It deletes that install's virtualenv and the temporary build files next to it, then stops. The shared download cache is left as it is.
- If the install log says setuptools found multiple top-level packages in a flat layout, the check does not try to install the project or only its dependencies. The reason is that the project is not installable as a Python package.
- Other "this is not a Python package" failures, such as an application that is meant to be set up with `uv sync`, still install only the declared dependencies. That earlier behaviour is unchanged.
- When a product check cannot verify because a test failed to import or collect, the gap step reads the pytest logs and the junit files, not only the short reason. The could-not-verify reason keeps that error text, so a missing module or a missing shared library is visible.
- That same error text is what the existing per-run lookup diagnoses. The lookup query uses the pytest or collection line. A missing system library, header or build tool still takes priority in that query. On a product check the result is could not verify, with a limitation that names the missing piece from the error text. This is the same on every sandbox, including Contree: the check does not try to install an OS package. The setup plan does not mark a system package as applied, and the Contree shell therefore has no apt install line. A system package the project's own files ask for is recorded as a could-not-verify limitation. This change does not add another retry loop or another installer. A Python requirement is installed only when that existing step already would: the error names a module the project declares (including an extra), or a link-back suggestion.
- Those declared requirements are read from main's checkout only. On a source comparison that is main's side. On a nightly run, main is the base-branch tree, not the pull-request head checked out for a source build. A dependency that appears only on the pull request is not trusted and is not installed.
- A flat-layout failure seen only while installing the pull-request side stays could not verify. It does not become needs attention, including when the log has an error line and both install tries ran.

A study run is unchanged. It does not use these stops, and it does not read pytest logs for a gap retry.

## Why

Some projects cannot be installed on this machine. A GPU stack downloads very large wheels until the disk is full, then the same download is tried again. A flat-layout tree is not one Python package, so another install attempt does not help. Separately, a could-not-verify result often said only "setup gap setup", because the real `No module named ...` line lived in the pytest log and the gap step never read it. The lookup then diagnosed the generic sentence instead of the error, so nothing useful was installed and the missing name was lost.

## Decision

- Detect these stops from the install log and from the project's required dependencies. Do not special-case a repository by name, and do not keep a table that maps an import name to a distribution name.
- An optional extra that mentions CUDA does not by itself stop the check. Only a required CUDA build does: `nvidia-*-cu*`, `cuda-*`, or a `+cu` wheel.
- A missing system library, header or build tool is read from the error text. The check does not keep a list that turns that error into an OS package name, and it does not install one. On a product check that is true for the setup plan as well as for a later failure: Contree does not run an OS install either.
- A dependency is trusted only when main's checkout declares it. The pull request's own dependency list is not a source for that install.
- Disk-full cleanup removes the unfinished virtualenv, the side's temporary directory, a private uv cache for that side, and pip or uv build directories in that side's home. It does not wipe the shared cache.
- The real pytest or collection error is part of the text the existing gap step already turns into a lookup query and a missing-name. The reason keeps that error next to the short name.
- The verdict stays could_not_verify. These stops reach that verdict before retries, with a plain reason. They do not mark the check verified.

## Alternatives and tradeoffs

Retrying a disk-full install can fill the disk further and does not change the outcome. Treating every "not a package" error as unsupported would also stop applications that install cleanly from their declared dependencies, so only the flat-layout error takes the new stop. Leaving the short "setup gap setup" reason would keep the report from saying what was missing. A second installer, or a fixed import-to-package table, would overlap the lookup step that already decides what to install for each run.

## What it means for you

A product check of a CUDA project, a flat-layout project, or an install that runs out of disk ends quickly with could_not_verify and a reason you can read. A package whose name only contains nvidia is still installed. A disk-full install does not leave its temporary build files behind. A missing import shows the pytest error in the reason, and that error is what the per-run lookup diagnoses. A missing system library, header or build tool stays could not verify, and the limitation names what the error said was missing, on every sandbox, including when the setup plan saw the package first. A dependency added only by the pull request is not installed. A flat layout on the pull-request side alone stays could not verify. A study run behaves as it did before, including a Contree setup that still applies a system package the project lists.
