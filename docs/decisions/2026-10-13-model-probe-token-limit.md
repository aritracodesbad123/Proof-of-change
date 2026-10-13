# Model-written probes: room to think, readable names, and a record of every reply

## What went wrong

When the checker asked the Nemotron model to write probes (small scripts that run the same inputs on the old and
the new code and compare the results), the request sometimes failed with an unhelpful "TypeError".

The cause: Nemotron "thinks" before it answers, and that thinking counts towards the reply's size limit. The limit
was 8,000 tokens (a token is roughly three-quarters of a word). On one benchmark case the model spent all 8,000
tokens thinking and stopped with the reason "length", so the answer itself was empty. Our code then tried to read
an empty answer as JSON, which is what raised the TypeError. Another case needed about 9,800 tokens, so it would
also have failed at the old limit.

A second problem showed up once the limit was raised: the model named its probes "P1" or "probe_get_x", but our
checker only accepts lower-case names with hyphens, so it threw away good probes just because of their names.

## What changed

1. **Bigger limit.** The default size limit for a model reply is now 32,000 tokens. It can be changed with the
   `POC_MAX_TOKENS` setting.
2. **Clear error.** If the model still returns no answer, the error now says so and gives the stop reason and the
   limit, instead of a bare TypeError.
3. **Names are tidied, not rejected.** A probe name like "P1" becomes "p1". The name is only used as a file name,
   so nothing else changes.
4. **Every reply is kept.** When `POC_RAW_DIR` is set, each model reply is saved exactly as the server sent it,
   with the model name the server reports, the stop reason and the token counts. This is what made the problem
   visible, and it is one of the conditions for calling a run blind.

The comparison runner for the published PatchGuru tool also got two fixes. Each case's model calls are now routed
and saved under that case (before, later cases reused the first case's settings). A model call that times out now
records "could not verify" for that case instead of stopping the whole run. A `--wheel` option lets it use a
released package when the machine cannot build the library from source.

## Trade-offs

- A bigger limit means some replies take longer and cost more. We chose that over silently losing probes.
- Tidying names is slightly more forgiving than before. The other checks on a probe (size, that it parses, no
  network, and so on) are unchanged.
- Saving raw replies uses disk space. It is off unless the setting is given.
- With a released package, PatchGuru's "before" environment is close to the real one but not the exact commit.
  Records using it say so.
