# The results page keeps its app script when font links are removed

## Decision

The replay build removes only the font links from the page. It no longer removes everything from the first font link to the end of the page head. The Pages workflow now fails if the built page has no module script.

## Why

The build tool adds the app script and stylesheet to the page head before this step runs. The old rule deleted them too, so the published results page loaded nothing and showed a blank screen.

## Effect

The published results page loads and renders. The page still loads no font host. Verdicts, the study and the console are unchanged.
