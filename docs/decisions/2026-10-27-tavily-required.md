# A product check needs the Tavily setup lookup

## What changed

A product check now refuses to start when `TAVILY_API_KEY` is missing or blank. The message is one line. It
names the variable and says a check cannot run without the setup lookup. It never prints the key.

A product check is one pull request started with `--product-check`: the operator console, the
request-a-check worker, a Codespace check, or the GitHub App. The daily study is not a product check.
It is the library sweep with no single pull request. A study run (a benchmark) does not call the lookup.
The daily study still skips it when the key is not set, and a failed lookup does not stop that run.

If the setup lookup fails while a product check is running, before a verdict exists, the check stops.
The result is could not verify, and the record stores the reason in plain words. The record also stores
the queries, how many results came back, and each source title and URL, so the report can show them.

Related public bug reports are quoted background for the advisory write-up. If that later lookup fails,
the reason is recorded and the reports are left out of the write-up. The verdict stays as the check
already decided.

On a hosted console the Tavily key is a private server setting, `TAVILY_API_KEY`. The start form does
not ask for one, and a typed value is not read. If the server key is missing, the check refuses with
one line that says the operator needs to set it. A Codespace or other local run still refuses when its
own key is missing.

## Why

The lookup used to be optional. A missing key wrote a skip line and the check continued. A person reading
the result could not tell that the setup sources had never been looked up. The same thing happened when
the setup call failed: the check kept going and the result looked finished.

A hosted console must not ask a visitor to type a Tavily key. That key belongs on the server.

## Decision

- Stop before a product check starts when `TAVILY_API_KEY` is missing or blank. Do not continue.
- Stop a product check that is already running when the setup lookup fails, before a verdict exists.
  Record could not verify and the reason. A valid response with zero hits is a finished lookup, not a failure.
- Store the queries, the result count, and the source titles and URLs on the result record.
- If the related-reports lookup fails after the verdict, record the redacted reason and leave that
  background out of the advisory write-up. Do not change the verdict.
- On a hosted console, use only the server's `TAVILY_API_KEY`. Do not show a Tavily field and do not
  read a typed value. Refuse with one line when the server key is missing.
- On a Codespace or other local run, keep the rule that a missing key refuses the check.
- Playing back the saved sample does not run a check, so it does not need the key.
- Leave study runs and the daily study as they are. The daily study is not a product check.

## Alternatives and tradeoffs

- Keep going and only print a warning. That is what the tool used to do. A warning in a long log is easy to
  miss, and the result still looks finished. Stopping is louder. A product check with a missing key produces
  no result until the key is set.
- Require the key for a study run and the daily study as well. Those runs are compared with earlier runs
  that did not depend on the lookup. Changing them would mix a setup failure into results that are meant to
  stay comparable.
- Ask each hosted visitor to type a key. That puts a server setting into the form. The hosted key stays
  on the server.
- Commit one shared key in the repository. That would expose the key. The operator sets it on the server.
  A person running a Codespace sets their own. Tavily keys are free.

## What it means for you

Set `TAVILY_API_KEY` before a product check. On a hosted console the operator sets it on the server. The
form does not ask for it. In a Codespace, set the recommended secret or type the key into the form. Keys
are free at https://app.tavily.com/. Do not commit a key. A study run and the daily study do not need
the key for this lookup.
