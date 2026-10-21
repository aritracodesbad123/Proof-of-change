# Related bug reports are background on a product check

## What changed

A product check can look up a few related public bug reports and hand them to the advisory AI as background. The operator console passes the switch, and so does a Codespace that starts that console and a request-a-check that uses the same command. The GitHub App passes it too. A study run and the daily study do not. A benchmark stays off even if the switch is present.

The lookup runs only when a Tavily key is set. With no key, the check prints one line and continues. The key is never printed. The text is shortened, the same page is kept once, and it is quoted as data rather than as instructions. It is not used to choose a package. An expected verdict is not sent in the query.

The verdict is decided before this text is attached. The verdict rule, its thresholds, and the probe freeze are unchanged.

## Why

A reviewer sometimes wants to see that a similar bug was already reported. That context is useful next to the advisory summary. It is not a test result, and a study has to measure the same work as before. Sending an expected verdict to a search would also give the lookup the answer the study is trying to score.

## Decision

- Turn the lookup on only for a product check that asks: the operator console, request-a-check, a Codespace running that console, and the GitHub App.
- Leave it off for a study run and the daily study. The switch defaults off. A benchmark ignores the switch.
- Call the existing Tavily lookup, and only when the key is set. Otherwise print one line and continue. Never print the key.
- Pass the text to the advisory AI as quoted background. Do not pass it into the verdict, and do not let it choose a package.
- Keep the query to the repository and the pull-request title. Do not send an expected verdict.

## Alternatives and tradeoffs

- Search on every run, including the study. The study would then depend on a live web call and could change from one day to the next. Leaving the switch off keeps those results comparable.
- Let the model treat the page as instructions. A public page can say anything. Quoting it, and deciding the verdict first, keeps the page from steering the result.
- Let the lookup name a package to install. A page can name an unrelated package. This lookup returns background text only.

## What it means for you

On a console check, a request-a-check, a Codespace, or a GitHub App check, set `TAVILY_API_KEY` when you want a few related public bug reports beside the advisory summary. Leave the key unset and the check says the lookup was skipped and continues. A study run and the daily study do not look these up. The verdict is the same whether or not the background is there.
