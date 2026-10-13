# Model must write at least one probe per testable claim

## What went wrong

After the token-limit fix, the model's probe replies arrived complete, but on some pull requests the answer was an
empty list: `{"probes": []}`. A probe is a small script run on the old and the new code so plain code can compare
what they print. With no probe, the check falls back to the project's own tests and the automatic probe, and a
change those do not exercise slips through as "verified".

## What changed

1. **A clear rule in the instructions.** The model is told that the files it sees are the ones the pull request
   changes, that it must write at least one probe for every testable claim, and that an empty list is not an
   acceptable answer. It is asked to call the functions the claim is about directly, with a spread of ordinary and
   edge-case inputs (zero, negative, fractional, empty, each accepted type and so on).
2. **The answer format requires it too.** The answer format sent to the model now says the probes list must have
   at least one item.
3. **One retry.** If the first answer still has no usable probe (empty, or every probe was rejected by our
   checks), the model is asked once more, with the same inputs plus a short note on why the first answer was
   unusable. There is never more than one retry.

## What stayed the same

- The retry goes through the same answer-key firewall as every other model request, and sees only the old-side
  code and the pull request's own title and description. Nothing from the new side and nothing from any answer key
  is added.
- The freeze rule is unchanged: probes are fingerprinted before the new side runs.
- The rule is written in general terms. It was not tuned on any benchmark case's expected result.

## Trade-offs

- A forced probe may sometimes be weak. That is acceptable: the existing checks (does it run the changed lines,
  is it informative) still mark weak probes, and plain code still decides the verdict.
- The retry can add one more model call (time and cost) on the cases where the first answer was empty.

## Addendum: pull requests with no testable claim, and older builds

- **No testable claim.** Sometimes the model finds nothing checkable in a pull request's text, even though the
  pull request changes source files. Before, that meant no probe at all. Now the model is still asked for at least
  one probe that calls the functions in the changed files with ordinary and edge-case inputs. That probe has no
  claim attached, so it does not "expect" anything; plain code just compares the old and new outputs.
- **Building older versions.** Building an older library version from source can fail when the build tools pick up
  today's packages (for example a NumPy 2 release that the old code cannot build against). An optional pins file
  (`POC_BUILD_CONSTRAINTS`) can now be given. The same pins are used to build and to install, on both sides, and by
  both comparison tools, so the comparison stays fair.
- **Scripts that arrive as one long line.** Sometimes the model escapes its script twice, so it arrives as a single
  line full of literal "\n" sequences and does not run. If a script fails to parse as is but parses once those
  sequences are turned into real line breaks, the fixed version is used. Otherwise it is rejected as before.
- **Libraries built with meson (pandas, scipy, scikit-learn).** Their "editable" install rebuilds parts of the
  library the first time it is imported, using build tools that, by default, only exist during the install and are
  deleted afterwards. Tests then failed to start. For these libraries the build tools are now installed into the
  test environment first, so the rebuild works. Other libraries are installed exactly as before.
