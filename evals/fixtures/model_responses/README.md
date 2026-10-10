# Recorded model responses (TEST FIXTURES)

`<owner>/<repo>/<pr>.json`, read by `--model-provider recorded` (`poc/model_provider.py`, `RecordedProvider`):

```json
{"_fixture": "TEST FIXTURE: ...", "model": null,
 "claims": {"claims": [...]},   // the claims response (CLAIMS_SCHEMA)
 "probes": {"probes": [...]}}   // the probes response (PROBES_SCHEMA)
```

Every file here is a test fixture and must say so in `_fixture` (the provider refuses files that do not). A fixture
is either a hand-made stand-in (`"model": null`) or a response recorded from a real model call (`"model"` names it).
Either way, probes written from it are labelled `model (recorded fixture, not blind)` in every record and report and
are excluded from blind-eval scoring (`evals/pr_metrics.py`), exactly like post-hoc fixed probes.
