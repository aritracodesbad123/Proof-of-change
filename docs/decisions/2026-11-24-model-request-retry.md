# A failed model request is retried, and 'AI unavailable' does not lower a result

## What changed

A claims-extraction or probe-generation request that fails for a short-lived reason is sent again, twice, with a
pause between tries. The short-lived reasons are an HTTP 5xx, HTTP 429, a timeout, a connection that dropped, and
a JSON body that arrived cut off. Each failed try is logged with the HTTP status when the provider sent one, or
with the error name otherwise. An HTTP 4xx other than 429, including a refused key, is not sent again.

When the tries are used up, the error on the run says `AI unavailable`. That sentence does not, by itself, lower
the verdict. The rule that a verified result needs an AI-written probe which ran a changed line is unchanged. It
still applies when a probe was written and did not run a changed line, and when a probe was written and then
rejected. It does not apply when no model probe was written because the request never completed. A result that
already needs attention stays there.

## Why

A claims request can fail once with an HTTP error and then the run has no claims and no probe. The tests had
already shown the change. The missing probe was the provider, not a probe that ran and missed the edit. Sending
the same request again covers the usual brief outage. A bad request is still not sent again, because repeating
it would get the same refusal.

## Decision

Retry only claims and probe requests, and only the failures listed above. Two retries, then stop. Log every
failed try. Put `AI unavailable` on the error. Leave the changed-line rule as it is. Put a verified result back
only when that rule lowered it, no model probe was written, and no probe was rejected. Do not raise a result
that was not verified, and do not lower one that was.

## Alternatives and tradeoffs

Retrying every model call, including the judge and the summary, would spend those calls on a failure that this
change does not cover. Retrying a 4xx would repeat a request the provider has already rejected. Treating every
missing probe as `AI unavailable` would verify a run whose probe was written and did not reach the change. The
changed-line rule still holds that run back.

## What it means for you

A brief outage during claims or probe writing is tried three times in all. The log names the status or the error
on each failed try. If the provider still does not answer, the run says `AI unavailable` and the verdict stays
what the tests and the other rules already gave. A probe that ran and missed the change still keeps a verified
result from standing.
