"""Model providers for claim extraction and probe writing.

    nebius    Nebius Token Factory (OpenAI-compatible chat completions, structured JSON output). The API key is read
              from NEBIUS_API_KEY in THIS (orchestrator) process only. It is never put into any environment handed to a
              sandboxed or untrusted process: guardrails/isolation.py builds those from an allowlist that does not
              contain it, and its secret-name check refuses any *_KEY variable.
    recorded  Recorded model responses from fixture files (evals/fixtures/model_responses/<owner>/<repo>/<pr>.json).
              They are TEST FIXTURES: probes written from them are labelled "model (recorded fixture, not blind)" in
              every record and report, and never count in blind-eval scoring. Used by tests and CI.
    none      No model: fixed probes only.

`select(name)` returns (provider or None, note). With nebius and no key, the run falls back to fixed probes only and
the note says so (it is copied into the record and the report).
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

BASE_URL = "https://api.tokenfactory.nebius.com/v1"
KEY_ENV = "NEBIUS_API_KEY"
# docs/REQUIREMENTS.md section 4a: Nemotron 3 Super 120B extracts claims and writes probes.
DEFAULT_MODELS = {"claims": "nvidia/nemotron-3-super-120b-a12b", "probes": "nvidia/nemotron-3-super-120b-a12b"}
RECORDED_DIR = Path(__file__).resolve().parent.parent / "evals" / "fixtures" / "model_responses"
FIXTURE_MARK = "TEST FIXTURE"
PROVIDERS = ("nebius", "recorded", "none")

CLAIMS_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["claims"],
    "properties": {"claims": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["id", "text", "source_quote", "testable", "expect"],
        "properties": {"id": {"type": "string"}, "text": {"type": "string"},
                       "source_quote": {"type": "string"}, "testable": {"type": "boolean"},
                       "expect": {"type": "string", "enum": ["same", "differs"]}}}}}}

PROBES_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["probes"],
    "properties": {"probes": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["id", "about", "claims", "code"],
        "properties": {"id": {"type": "string"}, "about": {"type": "string"},
                       "claims": {"type": "array", "items": {
                           "type": "object", "additionalProperties": False,
                           "required": ["id", "covers", "expect"],
                           "properties": {"id": {"type": "string"},
                                          "covers": {"type": "array", "items": {"type": "string"}},
                                          "expect": {"type": "string", "enum": ["same", "differs"]}}}},
                       "code": {"type": "string"}}}}}}

CLAIMS_PROMPT = """You read a pull request's title and description and list its testable claims about behaviour.
For each claim give: id (C1, C2, ...), text (one sentence), source_quote (copied exactly from the title or description),
testable (false if it cannot be checked by running code), expect: "differs" if the claim says behaviour changes
between the base and the PR, "same" if it says behaviour stays the same. Answer with JSON only."""

PROBES_PROMPT = """You write probes: small deterministic Python scripts that are run, unchanged, on the BASE side and on
the PR side of a pull request, and whose printed observations are compared by plain code. You see only the PR title
and description, the claims, and BASE-side source code. Rules for "code": standard library plus the package under
test only; fixed seeds; no network, no files outside the current directory, no clock, no randomness without a seed;
never assert or raise on purpose: record what you see. The LAST line printed must be one JSON object
{"observations": {"<name>": <JSON value>, ...}} with at most 50 short dotted observation names. Wrap calls that may
fail and record the exception type name instead. "claims" maps claim ids to the observation names they cover (fnmatch
patterns) and what the claim expects for them (same | differs). Answer with JSON only."""


class ProviderError(RuntimeError):
    pass


class Provider:
    name = "base"
    blind = False

    def __init__(self, models: dict | None = None):
        self.models = dict(DEFAULT_MODELS, **(models or {}))

    def complete_json(self, task: str, system: str, user: str, schema: dict, ctx: dict) -> dict:
        raise NotImplementedError

    def describe(self) -> dict:
        return {"provider": self.name, "models": self.models, "blind": self.blind}


class NebiusProvider(Provider):
    name = "nebius"
    blind = True

    def __init__(self, api_key: str, models: dict | None = None, base_url: str = BASE_URL, timeout: int = 180):
        super().__init__(models)
        self._key, self.base_url, self.timeout = api_key, base_url.rstrip("/"), timeout

    def complete_json(self, task: str, system: str, user: str, schema: dict, ctx: dict) -> dict:
        body = {"model": self.models[task], "temperature": 0, "max_tokens": 8000,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": task, "schema": schema, "strict": True}}}
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self._key}"},
                                     method="POST")  # br-allow-external: model inference call, creates nothing
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:   # noqa: S310 (fixed https URL)
                data = json.loads(r.read())
            return json.loads(data["choices"][0]["message"]["content"])
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"{self.name} {task} request failed: {type(e).__name__}") from None


class RecordedProvider(Provider):
    """Answers from evals/fixtures/model_responses/<owner>/<repo>/<pr>.json: {"_fixture": "TEST FIXTURE ...",
    "model": ..., "claims": <claims response>, "probes": <probes response>}."""
    name = "recorded"
    blind = False

    def __init__(self, root: Path = RECORDED_DIR, models: dict | None = None):
        super().__init__({k: "recorded-fixture" for k in DEFAULT_MODELS})   # never claims to be a real model run
        self.root = Path(root)

    def fixture(self, repo: str, pr: int) -> dict | None:
        f = self.root / repo / f"{pr}.json"
        if not f.is_file():
            return None
        d = json.loads(f.read_text())
        if FIXTURE_MARK not in str(d.get("_fixture", "")):
            raise ProviderError(f"{f.name}: recorded response is not labelled as a {FIXTURE_MARK}")
        return d

    def complete_json(self, task: str, system: str, user: str, schema: dict, ctx: dict) -> dict:
        d = self.fixture(ctx["repo"], ctx["pr"])
        if d is None or task not in d:
            raise ProviderError(f"no recorded {task} response for {ctx['repo']}#{ctx['pr']}")
        if d.get("model"):
            self.models = {k: d["model"] for k in self.models}
        return d[task]


def select(name: str, env: dict | None = None, models: dict | None = None,
           recorded_dir: Path | None = None) -> tuple[Provider | None, str]:
    env = os.environ if env is None else env
    if name == "none":
        return None, "model provider: none (--model-provider none): fixed probes only"
    if name == "recorded":
        return RecordedProvider(recorded_dir or RECORDED_DIR, models), (
            "model provider: recorded responses (TEST FIXTURE, not blind)")
    if name == "nebius":
        key = env.get(KEY_ENV)
        if not key:
            return None, f"model provider: nebius requested but {KEY_ENV} is not set: fixed probes only"
        return NebiusProvider(key, models), "model provider: nebius (Token Factory, live)"
    raise ValueError(f"unknown model provider {name!r}; one of {PROVIDERS}")
