# A product check needs the Tavily setup lookup

## What changed

A product check now refuses to start when `TAVILY_API_KEY` is missing or blank. The message is one line. It
names the variable and says a check cannot run without the setup lookup. It never prints the key.

A product check is a single pull request started from the operator console, the request-a-check worker, the
daily product check, a Codespace, or the GitHub App. If the lookup fails while that check is running (the
service returns an error, the call times out, or the response is empty or not usable), the check stops. The
result is could not verify, and the record stores the reason in plain words. The record also stores the
queries, how many results came back, and each source title and URL, so the report can show them.

A study run and the daily study are unchanged. A study run does not call the lookup. The daily study still
skips it when the key is not set, and a failed lookup does not stop that run.

## Why

The lookup used to be optional. A missing key wrote a skip line and the check continued. A person reading
the result could not tell that the setup sources had never been looked up. The same thing happened when the
call failed: the check kept going and the result looked finished.

## Decision

- Stop before a product check starts when `TAVILY_API_KEY` is missing or blank. Do not continue.
- Stop a product check that is already running when the lookup fails. Record could not verify and the reason.
  A valid response with zero hits is a finished lookup, not a failure.
- Store the queries, the result count, and the source titles and URLs on the result record.
- On the hosted console, only a key typed into the session counts. The server's key is not used for a
  visitor's check. With no typed key, the check is refused. A Codespace still accepts the `TAVILY_API_KEY`
  secret from the environment, because that secret belongs to the person running the Codespace.
- Playing back the saved sample does not run a check, so it does not need the key.
- Leave study runs and the daily study as they are.

## Alternatives and tradeoffs

- Keep going and only print a warning. That is what the tool used to do. A warning in a long log is easy to
  miss, and the result still looks finished. Stopping is louder. A product check with a missing key produces
  no result until the key is set.
- Require the key for a study run and the daily study as well. Those runs are compared with earlier runs
  that did not depend on the lookup. Changing them would mix a setup failure into results that are meant to
  stay comparable.
- Commit one shared key in the repository. That would expose the key. Each person sets their own. Tavily
  keys are free.

## What it means for you

Set `TAVILY_API_KEY` before a product check. In the console, type your own key into the start form. In a
Codespace, set the recommended secret or type the key into the form. Keys are free at
https://app.tavily.com/. Do not commit a key. A study run and the daily study do not need the key for this
lookup.
