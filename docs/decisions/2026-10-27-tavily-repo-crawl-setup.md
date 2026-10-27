# A product check crawls the pull request's own repository before it installs anything

## What changed

Before either side is installed, a product check now uses Tavily Crawl on the pull request's own GitHub
repository, pinned to the pull request's base commit (`github.com/<owner>/<repo>/tree/<base commit>`), and on
the project's own documentation site when its packaging metadata labels one. No other domain is crawled, and
any page outside that scope is dropped. The crawl instructions ask for install and development setup,
contributing and testing guides, test dependencies, the supported Python versions, pytest settings and the CI
workflow files. Tavily Extract then reads the full text of the key pages, including the setup files and CI
workflows the repository really has at that commit.

Setup steps are read from that text: extras, dependency groups, requirements files and named packages. A step
is kept only when the project's own files back it: the extra or group is declared, the requirements file
exists at that commit, or the package is one the project itself declares. Python versions and pytest settings
are recorded but are not install steps. Kept steps run first in the sandbox install, before the default
install, and a failed step is reported without stopping the install. Nothing in the code names a package or a
project, and no OS package is installed. Installs happen only inside the sandbox.

After the test tools are installed, the product install reinstalls the pull request's own checkout without
dependencies, so a test tool cannot replace it with a separately installed copy. Each side then imports the
package from the directory the tests run in and records its file path. If either side imports it from outside
the checkout, the check stops at could not verify with that reason.

When setup or test collection fails, the repair lookup now gets the real error line, never a banner such as
"ERRORS" or "ImportError while loading conftest", together with the crawled steps. A try that finds nothing to
install no longer ends the repair: the next try asks again from another angle, until all three tries are used.

Tavily stays required. With no key, or when every Tavily call fails, the check stops with "Tavily
unavailable" before any install. Each record stores the pages crawled, the pages read in full, every step with
the URL it came from and whether it was used, the number of Tavily calls and the credits they used.

Results are cached on disk by the exact repository and base commit, for seven days. A rerun at the same
repository and base commit reads the cache, makes no crawl or extract call and gets the same steps. Every new
base commit, even a newer tip of the same branch, pays for a full crawl. The record says whether the cache was hit. The
cache never changes a verdict.

Only product checks do this. A study run and the daily study are unchanged, and their install commands stay
exactly the same.

## Why

The earlier web search ran on every check but returned generic pages, often about other projects, and never
supplied a setup step the sandbox used. When setup failed, the repair sent a banner instead of the error and
gave up after one try. In one case the tests loaded a separately installed copy of the package, so a check
could pass without testing the change. Reading the project's own pages at the exact commit being tested is the
most direct source for its setup, and checking where the package is imported from makes sure the change is
what gets tested.

## Limits

A crawled step is only as good as the project's own pages. A step the project's files do not back is recorded
and not used. Setup will not always succeed. When it fails after three repair tries, the result says so.

## Review fixes

- A Tavily stop on the product route ends the check through the normal exit (`gate()`, then the caller's `finish()`), so record.json, the PDF and cleanup still happen. The record says could not verify with the "Tavily unavailable" reason.
- On GitHub only `/<owner>/<repo>/(tree|blob)/<base commit>/…` is in scope. Issues, pull requests, discussions, wikis and other branches are out, since anyone can write text there.
- The repair search is redacted before it is sent to Tavily.
- The import-origin check resolves the checkout path inside the sandbox (realpath), so a symlinked checkout still matches. A namespace package (no `__file__`) is reported as its own status and counts as in the checkout only when one of its paths is.
- The crawl cache key carries `CRAWL_VERSION`, so a code change does not reuse old crawls.
- A version pin taken from a crawled page is dropped (the package is kept) unless the project's own files list that exact pin.
- The crawl reads the main commit that is tested. The record keeps both `crawl_base_sha` and `checkout_sha`; if they differ, the crawled steps are not applied and the check stops at could not verify.
