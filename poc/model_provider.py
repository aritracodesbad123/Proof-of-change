"""Model providers for claim extraction and probe writing.

    nebius    Nebius Token Factory (OpenAI-compatible chat completions, structured JSON output). The API key is read
              from NEBIUS_API_KEY in THIS (orchestrator) process only. It is never put into any environment handed to a
              sandboxed or untrusted process: guardrails/isolation.py builds those from an allowlist that does not
              contain it, and its secret-name check refuses any *_KEY variable.
    recorded  Recorded model responses from fixture files (evals/fixtures/model_responses/<owner>/<repo>/<pr>.json).
              They are TEST FIXTURES: probes written from them are labelled "model (recorded fixture, not blind)" in
              every record and report, and never count in blind-eval scoring. Used by tests and CI.
    none      No model: fixed probes only.

`select(name)` returns (provider or None, note). It never includes the API key. A run that is set to nebius must
not start when the key is missing or empty: `key_refusal` names the variable and how to fix it, and the daily run
and the eval runners stop there. Before any case starts, `auth_refusal` makes one cheap authenticated call. If the
provider rejects the key (HTTP 401 or 403), the run stops, and the message never contains the key. A 401 or 403
during a case is `ProviderRejected`, which is not a `ProviderError`, so a caller that records an ordinary model
failure must let it through and stop the run. `select` still returns no provider and a note when the key is
missing, so a caller can see why. Only an explicit `none` is a run with the AI off.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://api.tokenfactory.nebius.com/v1"
KEY_ENV = "NEBIUS_API_KEY"
# docs/REQUIREMENTS.md section 4a: Nemotron roles on Token Factory.
DEFAULT_MODELS = {
    "claims": "nvidia/nemotron-3-super-120b-a12b",
    "probes": "nvidia/nemotron-3-super-120b-a12b",
    "judge": "nvidia/Nemotron-3-Ultra-550b-a55b",
    "helper": "nvidia/Nemotron-3_5-Lightning",
    "summary": "nvidia/nemotron-3-super-120b-a12b",
}
HELPER_FALLBACK = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
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
    "properties": {"probes": {"type": "array", "minItems": 1, "items": {
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
patterns) and what the claim expects for them (same | differs).
Coverage rule: the BASE-side files shown are the files the pull request changes. Write at least one probe for every
testable claim; an empty "probes" list is not an acceptable answer. Each probe must call the functions or methods the
claim is about directly, with several representative inputs and edge cases chosen generically from the code you see
(for example: zero, negative and positive numbers, whole and fractional values, true and false, None, empty and
non-empty containers, boundary sizes, each accepted input type, and a small numpy array or pandas value where the
code uses those), so that a change in behaviour would show up in the observations. If you
are unsure whether behaviour changes, still record the outputs: plain code decides. Answer with JSON only."""


class ProviderError(RuntimeError):
    pass


class ProviderRejected(Exception):
    """The provider refused the API key (HTTP 401 or 403).

    This is not a ProviderError. A caller that treats a failed model call as a per-case error must let this
    through and stop the run. The message names the HTTP status and the environment variable, and it never
    contains the key.
    """

    def __init__(self, status: int, *, starting: bool):
        self.status = int(status)
        self.starting = bool(starting)
        super().__init__(rejection_message(self.status, starting=self.starting))


def rejection_message(status: int, *, starting: bool) -> str:
    """Plain stop message for a rejected key. It never contains the key."""
    when = "before any case starts" if starting else "during the run"
    return (
        f"STOPPED: the Nebius provider rejected {KEY_ENV} (HTTP {int(status)}) {when}. "
        "The run will not continue. "
        f"Fix: set {KEY_ENV} to a key the provider accepts and run again, "
        "or pass --model-provider none if you mean to run with the AI off. "
        "The key is never printed."
    )


def _auth_status(exc: BaseException) -> int | None:
    """HTTP status when the provider refused the key. None for any other failure."""
    code = getattr(exc, "code", None)
    if code in (401, 403):
        return int(code)
    return None


class Provider:
    name = "base"
    blind = False

    def __init__(self, models: dict | None = None):
        self.models = dict(DEFAULT_MODELS, **(models or {}))
        self.calls: list[dict] = []  # {"task", "ok"} for calls this object actually made

    def _remember(self, task: str, ok: bool) -> None:
        """Record that this provider attempted one call. The entry never contains an API key."""
        self.calls.append({"task": task, "ok": bool(ok)})

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

    def confirm_key(self) -> None:
        """One cheap authenticated call (GET /models) before any case starts.

        HTTP 401 or 403 raises ProviderRejected. Any other failure is ignored: a later 401 or 403 still
        stops the run. This call is not an AI case call, so it is not added to the call list or the cost ledger.
        The key is sent only as the Authorization header and is never written into an error.
        """
        req = urllib.request.Request(f"{self.base_url}/models",
                                     headers={"Authorization": f"Bearer {self._key}"},
                                     method="GET")  # br-allow-external: key check, creates nothing
        try:
            with urllib.request.urlopen(req, timeout=min(int(self.timeout), 30)) as r:  # noqa: S310 (fixed https URL)
                r.read()
        except urllib.error.HTTPError as e:
            code = _auth_status(e)
            e.close()
            if code is not None:
                raise ProviderRejected(code, starting=True) from None
        except Exception:  # noqa: BLE001 — a models-list outage is not a rejected key
            return

    def complete_json(self, task: str, system: str, user: str, schema: dict, ctx: dict) -> dict:
        body = {"model": self.models[task], "temperature": 0,
                "max_tokens": int(os.environ.get("POC_MAX_TOKENS", "32000")),
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": task, "schema": schema, "strict": True}}}
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self._key}"},
                                     method="POST")  # br-allow-external: model inference call, creates nothing
        raw_dir = os.environ.get("POC_RAW_DIR")
        data, err = None, None
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:   # noqa: S310 (fixed https URL)
                data = json.loads(r.read())
            ch = data["choices"][0]
            if ch["message"].get("content") is None:
                # Nemotron reasons before answering; if reasoning uses the whole token budget the answer is empty
                err = f"no answer (finish_reason={ch.get('finish_reason')}, usage={data.get('usage')})"
                raise ProviderError(f"{self.name} {task}: model returned no answer "
                                    f"(finish_reason={ch.get('finish_reason')}; token limit {body['max_tokens']})")
            return json.loads(ch["message"]["content"])
        except ProviderRejected:
            raise
        except ProviderError:
            raise
        except Exception as e:  # noqa: BLE001
            status = _auth_status(e)
            if status is not None:
                err = f"HTTP {status}"
                raise ProviderRejected(status, starting=False) from None
            err = f"{type(e).__name__}: {e}"
            raise ProviderError(f"{self.name} {task} request failed: {type(e).__name__}") from None
        finally:
            self._remember(task, err is None)
            from poc import cost as _cost
            _cost.record_call((data or {}).get("model") or body["model"], (data or {}).get("usage"), ok=err is None)
            if raw_dir:
                import time as _t
                d = Path(raw_dir)
                d.mkdir(parents=True, exist_ok=True)
                ch = ((data or {}).get("choices") or [{}])[0]
                (d / f"{_t.strftime('%H%M%S')}-{task}-{os.getpid()}.json").write_text(json.dumps({
                    "task": task, "requested_model": body["model"], "max_tokens": body["max_tokens"],
                    "server_model": (data or {}).get("model"), "finish_reason": ch.get("finish_reason"),
                    "usage": (data or {}).get("usage"), "error": err, "raw": data}, indent=1))


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
        try:
            d = self.fixture(ctx["repo"], ctx["pr"])
            if d is None or task not in d:
                raise ProviderError(f"no recorded {task} response for {ctx['repo']}#{ctx['pr']}")
            if d.get("model"):
                self.models = {k: d["model"] for k in self.models}
            out = d[task]
        except ProviderError:
            self._remember(task, False)
            raise
        self._remember(task, True)
        return out


def select(name: str, env: dict | None = None, models: dict | None = None,
           recorded_dir: Path | None = None) -> tuple[Provider | None, str]:
    env = os.environ if env is None else env
    if name == "none":
        return None, "model provider: none (--model-provider none): the AI was off; fixed probes only"
    if name == "recorded":
        return RecordedProvider(recorded_dir or RECORDED_DIR, models), (
            "model provider: recorded responses (TEST FIXTURE, not blind)")
    if name == "nebius":
        raw = env.get(KEY_ENV) if KEY_ENV in env else None
        if raw is None:
            return None, f"model provider: nebius requested but {KEY_ENV} is not set: fixed probes only"
        if str(raw).strip() == "":
            return None, f"model provider: nebius requested but {KEY_ENV} is empty: fixed probes only"
        return NebiusProvider(raw if isinstance(raw, str) else str(raw), models), (
            "model provider: nebius (Token Factory, live)")
    raise ValueError(f"unknown model provider {name!r}; one of {PROVIDERS}")


def key_refusal(provider: str, env: dict | None = None) -> str | None:
    """Plain-language stop message when a Nebius run has no usable key. None if the run may start.

    `none` and `recorded` do not use the Nebius key. Only an explicit `none` is a run with the AI off.
    The message names the variable and how to fix it, and it never contains the key.
    """
    if provider != "nebius":
        return None
    env = os.environ if env is None else env
    raw = env.get(KEY_ENV) if KEY_ENV in env else None
    if raw is None:
        state = f"{KEY_ENV} is not set"
    elif str(raw).strip() == "":
        state = f"{KEY_ENV} is empty"
    else:
        return None
    return (
        f"STOPPED: this run is set to use the Nebius model provider, but {state}. "
        "The run will not start, because a run must not go ahead with the AI turned off. "
        f"Fix: set {KEY_ENV} to your Nebius Token Factory API key and run again, "
        "or pass --model-provider none if you mean to run with the AI off. "
        "The key is never printed."
    )


def auth_refusal(provider) -> str | None:
    """Plain stop message when a live Nebius provider rejects the key. None when the run may start.

    One cheap authenticated call (the models list). Only HTTP 401 and 403 stop the run. Any other failure
    of that call does not. `none` and `recorded` do not call the provider. The message never contains the key.
    """
    confirm = getattr(provider, "confirm_key", None)
    if not callable(confirm):
        return None
    try:
        confirm()
    except ProviderRejected as e:
        return str(e)
    return None


def describe_use(requested: str | None, provider, skipped: str | None = None,
                 fallback: str | None = None) -> dict:
    """What a result record should say about the provider that actually ran.

    `model_provider_used` is the provider that completed a call (`nebius`, `recorded`, or `none`).
    It is not the provider the run was asked for. `model_provider_fallback` is set when the AI was
    off, a call was skipped, or a call failed. Nothing here contains an API key.
    """
    requested = requested or "none"
    calls = list(getattr(provider, "calls", None) or [])
    ok = [c for c in calls if c.get("ok")]
    bad = [c for c in calls if not c.get("ok")]
    used = (getattr(provider, "name", None) or "none") if ok else "none"
    parts: list[str] = []
    if requested == "none":
        parts.append("the AI was off")
    if skipped:
        parts.append(skipped)
    if bad:
        tasks = ", ".join(dict.fromkeys(str(c.get("task") or "call") for c in bad))
        parts.append(f"AI call fell back or failed ({tasks})")
    if fallback:
        parts.append(fallback)
    if not parts and used == "none" and requested != "none":
        parts.append(f"no AI call ran (asked for {requested})")
    out = {"model_provider_used": used}
    seen: list[str] = []
    for part in parts:
        if part not in seen:
            seen.append(part)
    if seen:
        out["model_provider_fallback"] = "; ".join(seen)
    return out
