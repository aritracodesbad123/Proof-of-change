# Product checks on a component app install only the touched component's requirements

**Date:** 2026-10-22
**Status:** proposed

## What changed

Some projects are large applications made of many components or plugins. Each component declares its own requirements in a manifest next to its code, and the project also keeps an aggregate requirements file that collects every component's requirements. Installing that aggregate file means installing hundreds of libraries, most of them unrelated to the pull request, and the install fails or runs out of time.

On a product check (`--product-check` with `--pr`), the setup plan now does this:

- **Component manifests:** a folder whose `manifest.json` holds a `requirements` list is a component. That list is the component's own requirements. A `manifest.json` that is a symbolic link is ignored.
- **Aggregate files:** a top-level `requirements*.txt` is an aggregate when lines from at least two components' manifests appear in it and make up at least half of its lines. This is decided from the file's content, not its name. A project with fewer than three components, or with only one requirements file, has no aggregate file, so a small plugin project keeps installing its own requirements as before.
- **The touched component:** every changed file must belong to the same component. A file belongs when it is inside the component's folder, or inside a mirrored test folder for it (`tests/` followed by the component's path, or by the tail of that path). A folder elsewhere that only shares the component's name does not count. A changed path with a `..` part never belongs to any component. Aggregate files that a requirement bump regenerates are ignored.
- **Lint-only files:** a top-level requirements file whose every requirement is named in the project's own pre-commit configuration only pins lint hooks. It is not installed. This is decided from content, with no file or package names.
- **Off-index lines:** every manifest line of the touched component, every line of the core requirements files still installed, and every line of each file they include with `-r` or `-c` (followed recursively relative to the including file, with cycles stopped, and checked even when the included file is an aggregate or lint-only file) goes through the same refusal rules as other product-check installs (direct URLs, VCS, local paths and index options). An include with a `..` part, one that resolves outside the project (including through a symbolic link), or one that is missing is refused too. Any hit stops the check before installing, as could not verify with an `unsupported:` reason.
- **What gets installed:** the core requirements (the project's other requirements files, extras and dependency groups) plus that one component's manifest requirements. Everything is read from main's checkout, as for every other product-check install, so a pull request cannot add a requirement that then lands on main too.
- **Aggregate files on every route:** the aggregate files are left out of the setup plan, of the dependencies-only fallback plan used when a project cannot be built as a package, and of the same fallback inside the Contree sandbox.
- **No single component:** if the changed files touch more than one component, or files outside any component, the check stops before installing. The result is could not verify, with an `unsupported:` reason that names the aggregate files.
- **Other projects:** for a project with no aggregate file, nothing changes.

The study path is unchanged. It does not pass changed files, so this scoping never runs there, and the stop is only applied on the product route.

## Why the fallback stops instead of keeping the old behaviour

The old behaviour for these projects was to install the aggregate file. That is exactly what fails, and it pulls in many unrelated libraries from outside the change. Keeping it would spend the install time again and then still end as a setup failure. A clear `unsupported:` could-not-verify result is honest, it is fast, and it installs nothing the check cannot justify. Guessing a component or installing several components' requirements would be broader than what the pull request touches.

## Decision

- Use only the project's own per-component metadata and the pull request's changed paths. No project names, package names or per-repository special cases.
- Read every requirement from main.
- Fail closed when no single component can be found.
