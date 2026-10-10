"""The one choke point between a prompt and a model provider.

Every request to a model provider (a service that runs a language model, such as a hosted endpoint, or a recorded
stand-in used in tests) must pass the answer-key firewall (poc/leakage.check_bundle) first. To make that impossible
to skip, providers do not expose their raw call:

    class MyProvider(GatedProvider):
        def _call(self, task, system, user, schema, ctx):   # the real request; never called directly
            ...

    p = MyProvider(gate=Gate(fingerprints=Fingerprints.from_json(...), pr="owner/repo#1", base_root=old_checkout))
    p.complete_json("claims", system, user, schema, ctx)   # builds the bundle, checks it, THEN calls _call

* `GatedProvider.complete_json` is the only public entry point. It builds the prompt bundle from exactly what the
  provider will send (task, system prompt, user prompt, and any files in ctx["files"]), runs check_bundle, and calls
  `_call` only if the bundle passes. A refused bundle raises LeakageError and the provider is never contacted.
* A subclass that overrides `complete_json` is rejected when the class is defined, so the check cannot be skipped
  by accident.
* A provider without a Gate refuses every request (fail closed).
* The gate takes answer-key FINGERPRINTS (hashes, see `python -m poc.leakage fingerprint`), never an answer-key CSV
  path: generator code must not open an answer key. Without a benchmark, use `Gate.no_answer_key()`: the other
  rules (unknown keys, files that exist only on the new side or not in the old tree) still apply.

Wiring for the model-written-probes change (its `poc/model_provider.py` and `poc/model_probes.py`):

* `Provider` in poc/model_provider.py becomes a subclass of `GatedProvider`; `NebiusProvider.complete_json` and
  `RecordedProvider.complete_json` are renamed to `_call` (same arguments). `model_provider.select(...)` passes a
  `Gate` to the provider it builds: `Gate(fingerprints, pr="owner/repo#N", base_root=<old-side tree>,
  base_files=..., pr_files=...)` for benchmark runs, `Gate.no_answer_key(...)` for daily runs.
* `model_probes.generate(...)` keeps calling `provider.complete_json("claims", ...)` and
  `provider.complete_json("probes", ...)`. Those calls now pass through the gate. To get the file rules (files that
  exist only on the new side, or that are missing from the old tree), it should also put the old-side files it
  quotes into `ctx["files"]` as {relative path: content}.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from poc.leakage import Fingerprints, LeakageError, check_bundle


@dataclass
class Gate:
    fingerprints: Fingerprints
    pr: str | None = None
    base_files: set | None = None
    pr_files: set | None = None
    base_root: str | Path | None = None
    log: list = field(default_factory=list)   # one entry per checked request: task, ok, summary

    def __post_init__(self):
        if not isinstance(self.fingerprints, Fingerprints):
            raise TypeError("Gate needs answer-key Fingerprints (hashes), not a path: generator code never opens an "
                            "answer key")

    @classmethod
    def no_answer_key(cls, **kw) -> Gate:
        return cls(Fingerprints(source="(no answer key)"), **kw)

    def check(self, task: str, system: str, user: str, ctx: dict | None) -> dict:
        bundle = {"text": {"task": task, "system": system, "user": user}, "files": dict((ctx or {}).get("files") or {})}
        if self.pr:
            bundle["pr"] = self.pr
        try:
            res = check_bundle(bundle, self.fingerprints, self.base_files, self.pr_files, self.base_root)
        except LeakageError as e:
            self.log.append({"task": task, "ok": False, "why": str(e)})
            raise
        self.log.append({"task": task, "ok": True, "checked": res["checked"]})
        return res


class GatedProvider:
    """Base class for every model provider. Implement `_call`; callers use `complete_json`."""

    name = "gated"

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        if "complete_json" in cls.__dict__:
            raise TypeError(f"{cls.__name__} overrides complete_json; implement _call instead so every request "
                            "passes the answer-key firewall")

    def __init__(self, gate: Gate | None = None, models: dict | None = None):
        self.gate = gate
        self.models = models or {}

    def complete_json(self, task: str, system: str, user: str, schema: dict, ctx: dict | None = None) -> dict:
        if self.gate is None:
            raise LeakageError("no firewall gate configured for this provider; refusing to send anything")
        self.gate.check(task, system, user, ctx)
        return self._call(task, system, user, schema, ctx or {})

    def _call(self, task: str, system: str, user: str, schema: dict, ctx: dict) -> dict:  # pragma: no cover
        raise NotImplementedError
