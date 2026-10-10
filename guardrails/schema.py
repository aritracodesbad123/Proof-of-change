"""Schema validation for observation records.

Single source of truth: the shared JSON Schema `harness/schema/observation.schema.json`
(`$id` blast-radius/observation/v1, agreed with Jonathan, merged from feat/shared-schema @ ed75df4).
This module loads that file and validates against it with a small stdlib-only JSON Schema subset
(type, required, properties, items, enum, pattern, minimum, minLength), so it runs anywhere the
runner runs without a jsonschema dependency. Keywords outside that subset fail loudly at import.

Nathan extensions (kept here because the shared schema does not express them; documented in
docs/REQUIREMENTS.md section 9 "Schema"):
  E1  Validation modes. `v1` = the full shared schema. `ci` = records written by harness/run.py
      before v1 (no schema_version/accepted/gates/network/report) but with machine_type/thread_env.
      `legacy` = pre-harness records: additionally machine_type/thread_env not required.
      A record that declares `schema_version` is always validated in `v1` mode.
  E2  Cross-field rules from the schema's `x-cross-field-rules` that matter for evals: classification
      may be null only when accepted is false; import_failure/real_break are separate classes.
  E3  Schema reference by checksum. A record may name `schema_path` (often an absolute path in
      another checkout, e.g. /workspace/blast-radius/harness/schema/...). The path is NEVER opened;
      `schema_sha256` must equal the sha256 of this repo's copy instead.
  E4  JSON booleans are never accepted where an integer/number is required (JSON Schema semantics).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "harness" / "schema" / "observation.schema.json"
SCHEMA_BYTES = SCHEMA_PATH.read_bytes()
SCHEMA: dict = json.loads(SCHEMA_BYTES)
SCHEMA_SHA256 = hashlib.sha256(SCHEMA_BYTES).hexdigest()
SCHEMA_ID = SCHEMA.get("$id")

PROPS: dict = SCHEMA["properties"]
REQUIRED: tuple[str, ...] = tuple(SCHEMA["required"])
CLASS_KEYS: tuple[str, ...] = tuple(PROPS["classification"]["required"])
SINGLE_THREAD_VARS: tuple[str, ...] = tuple(PROPS["thread_env"]["required"])
EXPECTED_CLASSES = set(PROPS["expected_class"]["enum"])
MATCHES = set(PROPS["matches_expected"]["enum"])
REQUIRED_RUNS_PER_SIDE = 3  # protocol (x-cross-field-rules: runs_per_side >= 3); harness enforces exactly 3

CI_FIELDS = ("machine_type", "thread_env")
V1_ONLY_FIELDS = ("schema_version", "accepted", "gates", "network", "report")  # added by Jonathan's v1 runner
MODES = ("v1", "ci", "legacy")

_SUPPORTED = {"$schema", "$id", "title", "description", "type", "required", "properties", "items", "enum",
              "pattern", "minimum", "minLength", "x-cross-field-rules"}
_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float),
          "boolean": bool, "null": type(None)}


def _check_supported(node, where="$"):
    if isinstance(node, dict):
        unknown = set(node) - _SUPPORTED
        if unknown:
            raise ValueError(f"shared schema uses unsupported keywords at {where}: {sorted(unknown)}")
        for k, v in node.items():
            if k == "properties":
                for pk, pv in v.items():
                    _check_supported(pv, f"{where}.properties.{pk}")
            elif k == "items":
                _check_supported(v, f"{where}.items")


_check_supported(SCHEMA)


def _is_type(v, t: str) -> bool:
    if isinstance(v, bool) and t in ("integer", "number"):
        return False  # E4
    return isinstance(v, _TYPES[t])


def _validate(v, node: dict, where: str, skip_required: frozenset = frozenset()) -> list[str]:
    errs: list[str] = []
    types = node.get("type")
    if types is not None:
        tl = [types] if isinstance(types, str) else types
        if not any(_is_type(v, t) for t in tl):
            return [f"{where}: has type {type(v).__name__}, expected {'/'.join(tl)}"]
    if "enum" in node and v not in node["enum"]:
        errs.append(f"{where}: must be one of {node['enum']}, got {v!r}")
    if isinstance(v, str):
        if "minLength" in node and len(v) < node["minLength"]:
            errs.append(f"{where}: shorter than {node['minLength']}")
        if "pattern" in node and not re.search(node["pattern"], v):
            errs.append(f"{where}: {v!r} does not match {node['pattern']!r}")
    if isinstance(v, (int, float)) and not isinstance(v, bool) and "minimum" in node and v < node["minimum"]:
        errs.append(f"{where}: {v} < minimum {node['minimum']}")
    if isinstance(v, dict):
        for k in node.get("required", ()):
            if k not in v and k not in skip_required:
                errs.append(f"{where}: missing field '{k}'")
        for k, sub in node.get("properties", {}).items():
            if k in v:
                errs += _validate(v[k], sub, f"{where}.{k}" if where else k)
    if isinstance(v, list) and isinstance(node.get("items"), dict):
        for i, item in enumerate(v):
            errs += _validate(item, node["items"], f"{where}[{i}]")
    return errs


def mode_for(rec: dict, require_ci_fields: bool = True, require_v1: bool | None = None) -> str:
    if require_v1 or (isinstance(rec, dict) and "schema_version" in rec):
        return "v1"
    return "ci" if require_ci_fields else "legacy"


def check_schema_reference(rec: dict) -> list[str]:
    """E3: verify the record's schema reference by checksum, never by opening `schema_path`."""
    rid = rec.get("id", "<no id>")
    errs = []
    sha = rec.get("schema_sha256")
    if sha is not None and sha != SCHEMA_SHA256:
        errs.append(f"{rid}: schema_sha256 {str(sha)[:12]}... does not match the shared schema in this repo "
                    f"({SCHEMA_SHA256[:12]}...); record was written against a different schema version")
    if rec.get("schema_path") and sha is None:
        errs.append(f"{rid}: schema_path given without schema_sha256; cannot verify the reference")
    return errs


def validate_record(rec: dict, require_ci_fields: bool = True, require_v1: bool | None = None) -> list[str]:
    """Return a list of human-readable schema errors (empty list = valid).

    require_ci_fields=False -> legacy mode (pre-harness records). require_v1=True forces the full shared
    schema even if the record does not declare schema_version (golden batches).
    """
    if not isinstance(rec, dict):
        return ["record is not a JSON object"]
    rid = rec.get("id", "<no id>")
    mode = mode_for(rec, require_ci_fields, require_v1)
    skip = frozenset() if mode == "v1" else frozenset(V1_ONLY_FIELDS + (CI_FIELDS if mode == "legacy" else ()))
    errs = _validate(rec, SCHEMA, "", skip)
    errs = [f"{rid}: {e[2:] if e.startswith(': ') else e}" for e in errs]
    # E2: cross-field rules
    if rec.get("classification") is None and "classification" in rec and rec.get("accepted") is not False:
        errs.append(f"{rid}: classification may be null only when accepted is false")
    errs += check_schema_reference(rec)
    return errs
