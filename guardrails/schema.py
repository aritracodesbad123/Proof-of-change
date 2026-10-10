"""Schema validation for observation records.

Single source of truth: the shared JSON Schema `harness/schema/observation.schema.json`
(`$id` blast-radius/observation/v1, merged from feat/shared-schema @ ed75df4;
revision 2 adds OPTIONAL reviewer-report fields, see harness/schema/README.md).
This module loads that file and validates against it with a small stdlib-only JSON Schema subset
(type, required, properties, items, enum, const, pattern, minimum, minLength, if/then/else), so it runs anywhere the
runner runs without a jsonschema dependency. Keywords outside that subset fail loudly at import.

Extensions (kept here because the shared schema does not express them; documented in
docs/REQUIREMENTS.md section 9 "Schema"):
  E1  Validation modes. `v1` = the full shared schema. `ci` = records written by harness/run.py
      before v1 (no schema_version/accepted/gates/network/report) but with machine_type/thread_env.
      `legacy` = pre-harness records: additionally machine_type/thread_env not required.
      A record that declares `schema_version` is always validated in `v1` mode.
  E2  Cross-field rules from the schema's `x-cross-field-rules` that matter for evals: classification
      may be null only when accepted is false; import_failure/real_break are separate classes.
  E3  Schema reference by checksum. A record may name `schema_path` (often an absolute path in
      another checkout, e.g. /path/to/checkout/harness/schema/...). The path is NEVER opened;
      `schema_sha256` must be one of COMPATIBLE_SCHEMA_SHA256: this repo's copy, or an earlier
      revision that the current file only extends with optional fields (so the record is still valid).
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
SCHEMA_REVISION = max(r["rev"] for r in SCHEMA.get("x-revisions", [{"rev": 1}]))

# sha256 of every schema revision a record may name. Later revisions only ADD optional fields, so a record
# written against an earlier one is valid under the current file. Keep in sync with harness/schema/README.md.
SCHEMA_SHA256_REV1 = "5a3c3d36b7730ce74d0f23b03c88ea862ea35cc327c7d79481fca8b972e8383e"  # ed75df4
SCHEMA_SHA256_REV2 = "088cd395004de286c5f1df76fe94a0dc523738be194166cd3b616c77b6298183"  # + reviewer-report fields
SCHEMA_SHA256_REV3 = "2aafe631c82773d3258d531fb0e07c80ed7823d32fa3f4586d0d9e4a8e8916ca"  # + record_kind pr_run (if/then/else)
SCHEMA_SHA256_REV4 = "0a706f00904fa34ab8ad8bc7f79f53da08dd51576aa2800a3274befb95f7608d"  # + coverage-gate fields
SCHEMA_SHA256_REV5 = "f6c4e7ba5cd74c5c6259cf3311295a2cc909de20a6802d4b7c4496356c1448ea"  # + record_kind verification
COMPATIBLE_SCHEMA_SHA256 = {SCHEMA_SHA256_REV1: "rev 1", SCHEMA_SHA256_REV2: "rev 2", SCHEMA_SHA256_REV3: "rev 3",
                            SCHEMA_SHA256_REV4: "rev 4", SCHEMA_SHA256_REV5: "rev 5"}
if SCHEMA_SHA256 not in COMPATIBLE_SCHEMA_SHA256:
    raise RuntimeError(f"{SCHEMA_PATH} has sha256 {SCHEMA_SHA256}, which is not listed in COMPATIBLE_SCHEMA_SHA256; "
                       "add the new revision here and in harness/schema/README.md")

PROPS: dict = SCHEMA["properties"]


def observation_branch(schema: dict) -> dict:
    """The schema node with the observation-record rules: rev <= 2 the top level; rev 3/4 the `else` of
    `if record_kind == "pr_run"`; rev 5 one level further down (the `else` of `if record_kind == "verification"`)."""
    node = schema
    while "if" in node and isinstance(node.get("else"), dict):
        node = node["else"]
    return node


REQUIRED: tuple[str, ...] = tuple(SCHEMA.get("required") or observation_branch(SCHEMA).get("required", ()))
PR_RUN_REQUIRED: tuple[str, ...] = tuple(SCHEMA.get("then", {}).get("required", ()))
CLASS_KEYS: tuple[str, ...] = tuple(PROPS["classification"]["required"])
SINGLE_THREAD_VARS: tuple[str, ...] = tuple(PROPS["thread_env"]["required"])
EXPECTED_CLASSES = set(PROPS["expected_class"]["enum"])
MATCHES = set(PROPS["matches_expected"]["enum"])
REQUIRED_RUNS_PER_SIDE = 3  # protocol (x-cross-field-rules: runs_per_side >= 3); harness enforces exactly 3

CI_FIELDS = ("machine_type", "thread_env")
V1_ONLY_FIELDS = ("schema_version", "accepted", "gates", "network", "report")  # added by the v1 runner
MODES = ("v1", "ci", "legacy")

_SUPPORTED = {"$schema", "$id", "title", "description", "type", "required", "properties", "items", "enum",
              "pattern", "minimum", "minLength", "const", "if", "then", "else", "x-cross-field-rules", "x-revisions"}
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
            elif k in ("items", "if", "then", "else"):
                _check_supported(v, f"{where}.{k}")


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
    if "const" in node and v != node["const"]:
        errs.append(f"{where}: must be {node['const']!r}, got {v!r}")
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
    if "if" in node:  # rev 3: record_kind "pr_run" -> `then`, otherwise the observation rules in `else`
        branch = node.get("then") if not _validate(v, node["if"], where) else node.get("else")
        if branch:
            errs += _validate(v, branch, where, skip_required)
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
    if sha is not None and sha not in COMPATIBLE_SCHEMA_SHA256:
        errs.append(f"{rid}: schema_sha256 {str(sha)[:12]}... is not a known revision of the shared schema "
                    f"(current {SCHEMA_SHA256[:12]}...); record was written against an incompatible schema")
    if rec.get("schema_path") and sha is None:
        errs.append(f"{rid}: schema_path given without schema_sha256; cannot verify the reference")
    return errs


def schema_reference_note(rec: dict) -> str:
    """Human-readable note on which schema revision a record names (for reports)."""
    sha = rec.get("schema_sha256")
    if not sha:
        return "no schema_sha256 in record"
    rev = COMPATIBLE_SCHEMA_SHA256.get(sha)
    if rev is None:
        return f"unknown schema sha256 {sha[:12]}..."
    cur = COMPATIBLE_SCHEMA_SHA256[SCHEMA_SHA256]
    return f"written against {rev} (sha256 {sha[:12]}...)" + ("" if rev == cur else f"; valid under current {cur} (additive)")


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
