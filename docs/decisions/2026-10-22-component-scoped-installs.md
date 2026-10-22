# Product checks on a component app install only the touched component's requirements

**Date:** 2026-10-22
**Status:** proposed

## What changed

Some projects are large applications made of many components or plugins. Each component declares its own requirements in a manifest next to its code, and the project also keeps an aggregate requirements file that collects every component's requirements. Installing that aggregate file means installing hundreds of libraries, most of them unrelated to the pull request, and the install fails or runs out of time.

On a product check (`--product-check` with `--pr`), the setup plan now does this:

- **Component manifests:** a folder whose `manifest.json` holds a `requirements` list is a component. That list is the component's own requirements.
- **Aggregate files:** a top-level `requirements*.txt` is an aggregate when lines from at least two components' manifests appear in it and make up at least half of its lines. This is decided from the file's content, not its name.
- **The touched component:** every changed file must belong to the same component. A file belongs when it is inside the component's folder, or when one of its folder names is the component's folder name (tests kept in a mirrored tree). Aggregate files that a requirement bump regenerates are ignored.
- **What gets installed:** the core requirements (the project's other requirements files, extras and dependency groups) plus that one component's manifest requirements. Everything is read from main's checkout, as for every other product-check install, so a pull request cannot add a requirement that then lands on main too. The aggregate files are never installed.
- **No single component:** if the changed files touch more than one component, or files outside any component, the check stops before installing. The result is could not verify, with an `unsupported:` reason that names the aggregate files.
- **Other projects:** for a project with no aggregate file, nothing changes.

The study path is unchanged. It does not pass changed files, so this scoping never runs there, and the stop is only applied on the product route.

## Why the fallback stops instead of keeping the old behaviour

The old behaviour for these projects was to install the aggregate file. That is exactly what fails, and it pulls in many unrelated libraries from outside the change. Keeping it would spend the install time again and then still end as a setup failure. A clear `unsupported:` could-not-verify result is honest, it is fast, and it installs nothing the check cannot justify. Guessing a component or installing several components' requirements would be broader than what the pull request touches.

## Decision

- Use only the project's own per-component metadata and the pull request's changed paths. No project names, package names or per-repository special cases.
- Read every requirement from main.
- Fail closed when no single component can be found.
