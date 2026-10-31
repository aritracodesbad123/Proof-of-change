"""Probes: small deterministic Python scripts run on BOTH sides of a PR, compared by plain code.

Interface (the same for the fixed probe library today and for model-written probes later)
----------------------------------------------------------------------------------------
A probe is one Python file. It must:

* define a literal dict ``PROBE`` (read with ``ast.literal_eval``; the file is never imported by the harness):

    PROBE = {
        "id": "short-name",                     # unique within the PR
        "target": "owner/repo#123",              # the PR it was written for
        "about": "one sentence: what it observes",
        "claims": [                              # the PR's claims this probe can check (may be empty)
            {"id": "C1", "source": "PR description", "text": "...",
             "covers": ["observation.name", "prefix.*"],   # fnmatch patterns over observation names
             "expect": "differs" | "same"},                # what the claim says about main vs PR
        ],
        "timeout_s": 120,                        # optional
    }

* when run as ``python <file>`` with the side's interpreter (cwd: an empty folder, thread counts pinned to 1,
  no credentials in the environment), print ONE JSON object as its last line:
  ``{"observations": {"<name>": <any JSON value>, ...}}``. It must be deterministic (fixed seeds, no clock, no
  network) and must not assert: it reports what it saw.

Fixed probes live in ``probes/<owner>/<repo>/<pr>.py`` (more probes for the same PR: ``<pr>-<name>.py``).
A model-written probe (poc/model_probes.py) is the same kind of file, saved in the run folder with source "model";
a differential probe (poc/diff_probes.py, the tests+diff baseline) has source "diff".

Freeze rule (poc/freeze.py): every probe is frozen before any PR-side execution and `guard` re-checks it before each
PR-side run; a probe that fails the check is not run on the PR side.

Output contract (checked for every probe, `observations_of`): stdout at most MAX_OUTPUT_BYTES; the last line one JSON
object {"observations": {...}} with at most MAX_OBSERVATIONS names, each a string of at most 200 characters. A run
that breaks the contract becomes one PROBE_ERROR observation saying why.

Judging (``judge``): each observation is compared over 3 alternating runs per side with ``poc.diff.confirm``
(same / differs / flaky). Field-level differences come from ``poc.diff.compare``. Labels:

    same,    claim expects same     -> proven            differs, claim expects differs -> proven
    same,    no claim               -> no_difference     differs, claim expects same    -> false_claim
    same,    claim expects differs  -> needs_human       differs, no claim              -> unmentioned
    flaky                           -> flaky             probe crashed on both sides    -> not_testable

Any red or amber label (false_claim, unmentioned, needs_human) makes the PR verdict needs_attention, except two
cases kept at could_not_verify: tests collected nothing on both sides, and a differs claim whose only probe used
inputs where the old and new code agree because it never reached the change. A differs claim whose covered
observations all agree is advisory, and does not raise needs_attention, when another differs claim on the same
record is already proven: the claim was not shown on these inputs, and a related change was proven. With no
proven differs claim, that case still needs attention. Flaky
observations are ignored as noise when the base side is unstable or both sides are. An observation that is stable
on the base and unstable only on the pull request is not that noise: it needs attention, or could not verify when
every pull-request run differs. Differences that are only about warnings never count on their own.
"""
from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import re
import resource
import subprocess
import tempfile
import time
from pathlib import Path

from poc.diff import compare, confirm, parse_probe_output, pr_runs_too_noisy
from poc.verdict import COLOUR, FindingLabel

PROBES_DIR = Path(__file__).resolve().parent.parent / "probes"
PROBE_ERROR = "probe.error"   # observation name used when a run printed no usable observations
ABSENT = "<absent>"
DEFAULT_TIMEOUT = 120
MAX_TIMEOUT = 300
MAX_OUTPUT_BYTES = 256_000
MAX_OBSERVATIONS = 200


class ProbeError(ValueError):
    pass


def read_spec(path: Path) -> dict:
    """The PROBE dict of a probe file, validated. The file is parsed, never imported."""
    src = Path(path).read_text()
    spec = None
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PROBE" for t in node.targets):
            spec = ast.literal_eval(node.value)
    if not isinstance(spec, dict):
        raise ProbeError(f"{path}: no literal PROBE dict")
    for k in ("id", "target", "about"):
        if not isinstance(spec.get(k), str) or not spec[k]:
            raise ProbeError(f"{path}: PROBE[{k!r}] must be a non-empty string")
    claims = spec.setdefault("claims", [])
    for c in claims:
        if not {"id", "text", "covers", "expect"} <= set(c) or c["expect"] not in ("same", "differs"):
            raise ProbeError(f"{path}: claim {c.get('id')!r} needs id, text, covers and expect (same|differs)")
    spec.setdefault("timeout_s", DEFAULT_TIMEOUT)
    if not isinstance(spec["timeout_s"], int) or spec["timeout_s"] < 1:
        raise ProbeError(f"{path}: timeout_s must be a positive integer")
    spec["timeout_s"] = min(spec["timeout_s"], MAX_TIMEOUT)
    spec["sha256"] = hashlib.sha256(src.encode()).hexdigest()
    return spec


def find_probes(repo: str, pr: int, root: Path = PROBES_DIR) -> list[Path]:
    """Fixed probes for a PR: probes/<owner>/<repo>/<pr>.py and <pr>-*.py."""
    d = Path(root) / repo
    if not d.is_dir():
        return []
    return sorted([p for p in d.glob(f"{pr}.py")] + [p for p in d.glob(f"{pr}-*.py")])


_JSON_SCALARS = (str, int, float, bool, type(None))


def _json_shaped(v, depth: int = 0) -> bool:
    """True when v holds only what JSON itself can say: dicts with string keys, lists, strings, finite numbers,
    true, false and null. Tuples, sets, bytes, complex numbers, NaN and infinity are not: they would change on
    the way to JSON, so they make the output ambiguous."""
    if depth > 32:
        return False
    if isinstance(v, float):
        return v == v and v not in (float("inf"), float("-inf"))
    if isinstance(v, _JSON_SCALARS):
        return True
    if type(v) is list:
        return all(_json_shaped(x, depth + 1) for x in v)
    if type(v) is dict:
        return all(isinstance(k, str) and _json_shaped(x, depth + 1) for k, x in v.items())
    return False


def literal_observations(stdout: str):
    """Product checks only. The observations object when the probe's last line is a Python literal of exactly
    {'observations': {...}} (what print(dict) shows) holding only JSON-shaped values; else None.

    Fails closed: any other shape, any extra key, a value JSON cannot hold as is, or a line that is not a plain
    literal stays unparsed. The line is read with ast.literal_eval, never run."""
    lines = [ln for ln in (stdout or "").strip().splitlines() if ln.strip()]
    if not lines:
        return None
    last = lines[-1].strip()
    if not (last.startswith("{") and last.endswith("}")):
        return None
    try:
        obj = ast.literal_eval(last)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None
    if type(obj) is not dict or set(obj) != {"observations"} or type(obj["observations"]) is not dict:
        return None
    if not _json_shaped(obj):
        return None
    return obj


def observations_of(stdout: str, exit_code, literal_output: bool = False) -> dict:
    """{name: value} from one probe run. A run without usable observations becomes one PROBE_ERROR observation.

    literal_output: when the last line is not JSON, also accept a Python literal of the same
    {"observations": {...}} object (see literal_observations). Study runs and product checks both pass True.
    The default stays off, so a caller that does not ask still accepts JSON only."""
    if len(stdout.encode(errors="replace")) > MAX_OUTPUT_BYTES:
        return {PROBE_ERROR: {"contract": f"output larger than {MAX_OUTPUT_BYTES} bytes", "exit_code": exit_code}}
    obj = parse_probe_output(stdout, exit_code)
    if literal_output and obj.get("crash") == "non-json output":
        lit = literal_observations(stdout)
        if lit is not None:
            obj = lit if exit_code in (0, "0") else dict(lit, exit_code=exit_code)
    obs = obj.get("observations") if isinstance(obj, dict) else None
    if not isinstance(obs, dict) or "crash" in obj or "timeout" in obj:
        return {PROBE_ERROR: {k: v for k, v in obj.items() if k != "observations"} or {"crash": "no observations"}}
    if len(obs) > MAX_OBSERVATIONS or not all(isinstance(k, str) and 0 < len(k) <= 200 for k in obs):
        return {PROBE_ERROR: {"contract": f"observations must be at most {MAX_OBSERVATIONS} names of 1-200 characters",
                              "exit_code": exit_code}}
    if exit_code not in (0, "0"):
        obs = dict(obs, **{PROBE_ERROR: {"exit_code": exit_code}})
    return obs


def output_lines(obs: dict) -> list[str]:
    """Canonical saved form, one observation per line, so each observation can be cited by file and line."""
    return [json.dumps({"observation": k, "value": obs[k]}, sort_keys=True) for k in sorted(obs)]


def write_output(path: Path, obs: dict) -> None:
    Path(path).write_text("\n".join(output_lines(obs)) + "\n")


def read_output(path: Path) -> dict:
    out = {}
    for ln in Path(path).read_text().splitlines():
        if ln.strip():
            d = json.loads(ln)
            out[d["observation"]] = d["value"]
    return out


def citation(fname: str, obs: dict, name: str) -> dict | None:
    """{file, line, quote} of an observation in a saved output file (see output_lines)."""
    for i, ln in enumerate(output_lines(obs), 1):
        if json.loads(ln)["observation"] == name:
            return {"file": fname, "line": i, "quote": json.dumps({"observation": name})[1:-1]}
    return None


def claim_for(spec: dict, name: str) -> dict | None:
    """The claim an observation belongs to. When several claims cover the name, the most specific one wins: a cover
    equal to the name beats a wildcard match, then the claim with fewer cover patterns, then the first claim."""
    best, rank = None, None
    for i, c in enumerate(spec.get("claims", []) or []):
        if not isinstance(c, dict) or not _covers_name(c.get("covers"), name):
            continue
        covers = [p for p in c.get("covers") or [] if isinstance(p, str)]
        r = (0 if name in covers else 1, len(covers), i)
        if rank is None or r < rank:
            best, rank = c, r
    return best


def _covers_name(covers, name: str) -> bool:
    return any(isinstance(pat, str) and fnmatch.fnmatchcase(name, pat) for pat in covers or [])


def _observation_names(item: dict) -> list[str]:
    return [o.get("name") for o in (item.get("observations") or [])
            if isinstance(o, dict) and isinstance(o.get("name"), str)]


def rejection_reason(item: dict) -> str | None:
    """Why this probe's claim patterns match none of its own observation names, or None if it may count.

    A probe with no claims is not this case. One pattern that matches one observation name is enough to keep it.
    """
    claims = [c for c in (item.get("claims") or []) if isinstance(c, dict)]
    if not claims:
        return None
    names = _observation_names(item)
    for c in claims:
        if any(_covers_name(c.get("covers"), n) for n in names):
            return None
    ids = ", ".join(str(c.get("id") or "claim") for c in claims)
    return (f"rejected: claim pattern(s) {ids} match none of this probe's observation names, "
            f"so the probe is not counted")


def _counted_or_rejected(out: dict) -> dict:
    """A probe that ran still does not count when its claim patterns match nothing it observed."""
    why = rejection_reason(out)
    if why:
        out["status"] = "rejected"
        out["rejected_reason"] = why
        return out
    out["status"] = "ran"
    return out


def unmatched_differs_claims(probe_results: dict | None) -> list[str]:
    """Claim ids that expect a difference and match no observation name on that same probe.

    A claim in that state was never checked. It must not support a verified verdict."""
    found = []
    for it in (probe_results or {}).get("items") or []:
        if not isinstance(it, dict):
            continue
        names = _observation_names(it)
        for c in it.get("claims") or []:
            if not isinstance(c, dict) or c.get("expect") != "differs" or is_how_claim(c):
                continue
            if any(_covers_name(c.get("covers"), n) for n in names):
                continue
            found.append(str(c.get("id") or "claim"))
    return found


# A claim that only says how the fix works ("is processed by `_as_list()`", "now calls `x`"): it names code, not a
# behaviour. Calling that code gives the same result on both sides, so "no difference" says nothing against it.
_HOW_RE = re.compile(
    r"(?:\b(?:is|are|gets?|get|now|will be|being)\s+(?:\w+ly\s+)?(?:processed|handled|parsed|passed|routed|delegated|"
    r"converted|normali[sz]ed|computed|implemented|done|dispatched|wrapped)\s+(?:by|via|through|using|with|in)\s+"
    r"|\b(?:uses|calls|now calls|delegates to|goes through|is routed through|reuses|relies on)\s+(?:the\s+)?)"
    r"(?:`[^`]+`|[A-Za-z_][\w.]*\(\))", re.I)


def is_how_claim(claim: dict | None) -> bool:
    """True for a claim that only describes how the fix works, naming the code it goes through."""
    return bool(claim) and claim.get("expect") == "differs" and bool(_HOW_RE.search(str(claim.get("text") or "")))


# Observation names may carry claim ids in any case: "c2.x", "C2_x", or several joined ("c1_c2.result").
_ID_RE = re.compile(r"[A-Za-z]{1,8}\d+")


def _name_ids(spec: dict, name: str) -> list[str]:
    """The claim ids an observation name starts with, lower case, or [] when it starts with none.

    The first dot-separated segment is read. When it is only this probe's own name ("probe1" for probe
    "model-probe1") and that name is not also one of its claim ids ("model-c4" with claim C4), the next one
    is. The segment's leading "_"/"-" separated parts that look like ids are the ids ("c1_c2" -> c1, c2;
    "C1_x" -> c1). Something must follow them (a separator or more text): a bare "c1" is not a link."""
    segs = name.split(".")
    own = str(spec.get("id") or "").lower().removeprefix("model-")
    claim_ids = {str(c.get("id") or "").lower() for c in spec.get("claims") or [] if isinstance(c, dict)}
    if own and len(segs) > 1 and segs[0].lower() == own and own not in claim_ids:
        segs = segs[1:]
    parts = re.split(r"[_-]", segs[0])
    ids = []
    for part in parts:
        if not _ID_RE.fullmatch(part):
            break
        ids.append(part.lower())
    if not ids or (len(ids) == len(parts) and len(segs) == 1):
        return []
    return ids


def _text_link(spec: dict, name: str) -> str | None:
    """"id" when a model probe's observation name starts with claim ids that are ALL exact, full ids of this probe's
    own claims, number included, in any case ("c1.x" or "C1_x" next to claim "C1"; "c1_c2.result" next to claims C1
    and C2), but the name matches no cover. One id that is not this probe's claim breaks the link: "c9.x" next to
    only "C1", or "c1_c9.x" next to "C1", is not linked and still flags. A word shared with a claim's text is never
    a link: that would hide real unclaimed changes."""
    if spec.get("source") != "model" or not spec.get("claims"):
        return None
    found = _name_ids(spec, name)
    if not found:
        return None
    ids = {str(c.get("id") or "").lower() for c in spec["claims"] if isinstance(c, dict)}
    return "id" if all(i in ids for i in found) else None


def label_for(state: str, claim: dict | None, name: str, crashed_both: bool) -> str:
    if state == "flaky":
        return FindingLabel.FLAKY.value
    if name == PROBE_ERROR and crashed_both:
        return FindingLabel.NOT_TESTABLE.value
    if claim is None:
        return (FindingLabel.NO_DIFFERENCE if state == "same" else FindingLabel.UNMENTIONED_CHANGE).value
    if state == claim["expect"]:
        return FindingLabel.PROVEN.value
    if state == "same" and is_how_claim(claim):
        return FindingLabel.NOT_TESTABLE.value
    return (FindingLabel.FALSE_CLAIM if claim["expect"] == "same" else FindingLabel.NEEDS_HUMAN).value


def probe_broken(main, pr) -> bool:
    """The probe never reached the call it is about: the observation is the same raised exception type, or the same
    skip value, on both sides. That says nothing about the change, so it is 'probe broken': never 'does not differ'
    and never 'proven'."""
    exc = _exception_name(main) or _error_text(main)
    if exc and exc == (_exception_name(pr) or _error_text(pr)):
        return True
    return (isinstance(main, dict) and isinstance(pr, dict) and "skipped" in main
            and main.get("skipped") == pr.get("skipped"))


_ERROR_TEXT = re.compile(r"(?:[A-Za-z_][\w.]*\.)?([A-Z]\w*(?:Error|Exception|Failure))(?::.*)?|(skip(?:ped)?\b.*)",
                         re.IGNORECASE | re.DOTALL)


def _error_text(value) -> str | None:
    """A probe that records a failure as plain text: an exception type name ('TypeError', 'TypeError: msg',
    'SkippedDueToClassCreationFailure') or a skip note ('skipped: ...'). Returns the type name or skip note."""
    if not isinstance(value, str) or len(value) > 500:
        return None
    m = _ERROR_TEXT.fullmatch(value.strip())
    if not m:
        return None
    if m.group(1) and not m.group(1)[0].isupper():
        return None
    return m.group(1) or m.group(2).lower()


def judge(spec: dict, runs: dict, files: dict | None = None) -> list[dict]:
    """runs = {"main": [obs, obs, obs], "pr": [...]} -> one result per observation name (sorted).
    files = {"main": [file names], "pr": [...]} of the saved outputs, for citations."""
    names = sorted(set().union(*[set(o) for side in ("main", "pr") for o in runs[side]]))
    crashed_both = all(PROBE_ERROR in o for side in ("main", "pr") for o in runs[side])
    out = []
    for name in names:
        m = [{"v": o.get(name, ABSENT)} for o in runs["main"]]
        p = [{"v": o.get(name, ABSENT)} for o in runs["pr"]]
        state = confirm(m, p)
        claim = claim_for(spec, name)
        pr_only, broken = None, False
        if state == "pr_unstable":
            # Stored state stays "flaky" (the recorded vocabulary). The label is what the verdict reads.
            if pr_runs_too_noisy(p):
                pr_only, state = "noisy", "flaky"
                # Not "flaky": that label is noise. This one stays visible to later checks.
                label = FindingLabel.UNSTABLE_ON_PR.value
            else:
                pr_only, state = "regression", "flaky"
                if claim is None:
                    label = FindingLabel.UNMENTIONED_CHANGE.value
                elif claim["expect"] == "same":
                    label = FindingLabel.FALSE_CLAIM.value
                else:
                    label = FindingLabel.NEEDS_HUMAN.value
        else:
            label = label_for(state, claim, name, crashed_both)
            broken = state == "same" and probe_broken(m[0]["v"], p[0]["v"])
            if broken:
                label = FindingLabel.NOT_TESTABLE.value   # probe broken: advisory only, never a pass or a flag
        res = {"name": name, "state": state, "label": label,
               "claim": claim["id"] if claim else None,
               "main": m[0]["v"], "pr": p[0]["v"]}
        if pr_only:
            res["pr_only"] = pr_only
        if broken:
            res["probe_broken"] = "the same exception or skip value on both sides: the probe never reached the call"
        if label == FindingLabel.NOT_TESTABLE.value and state == "same" and is_how_claim(claim):
            res["how_claim"] = True
        link = _text_link(spec, name) if label == FindingLabel.UNMENTIONED_CHANGE.value else None
        if link:
            # The name starts with the full id of one of this probe's claims but matches no cover: shown as advisory
            # ("linked by claim id, check"), not as unclaimed. Claim text is never used for linking.
            res["advisory"] = True
            res["linked_by"] = link
        if state != "same":
            res["diffs"] = [dict(d, field=d["field"].split(".", 1)[1] if "." in d["field"] else "")
                            for d in compare({"v": m[0]["v"]}, {"v": p[0]["v"]})]
        if files:
            res["citations"] = {side: citation(files[side][0], runs[side][0], name) for side in ("main", "pr")
                                if name in runs[side][0]}
        out.append(res)
    _one_side_claim_link(spec, out)
    _link_split_raise_value(spec, out)
    _shape_link(out)
    _dangling_cover_link(spec, out)
    return out


DANGLING_NOTE = "the probe's only claim names none of its observations, so this difference is probably that claim, check"


def _dangling_cover_link(spec: dict, out: list[dict]) -> None:
    """A probe with exactly one claim, a difference claim whose cover patterns match none of the probe's observation
    names (a cover that repeats the claim id, or a prefix the probe never printed): its unclaimed differences are
    advisory ("probably that claim, check"), not unclaimed. They stay unmentioned and visible, and cap the verdict at
    could_not_verify; they are never proven. Probes with no claims, or with several, are unchanged, and differences
    unstable only on the PR are never linked."""
    claims = [c for c in spec.get("claims") or [] if isinstance(c, dict)]
    if len(claims) != 1 or claims[0].get("expect") != "differs":
        return
    if any(_covers_name(claims[0].get("covers"), r.get("name")) for r in out):
        return
    # Only a difference whose name starts with the claim id or with the first part of one of its covers
    # ("c1.x" next to claim C1, "result.x" next to cover "result.y") is linked. Any other difference in the probe
    # stays unclaimed and still needs attention.
    heads = {_name_head(claims[0].get("id"))} | {_name_head(c) for c in claims[0].get("covers") or [] if isinstance(c, str)}
    heads -= {""}
    for r in out:
        if (r.get("label") == FindingLabel.UNMENTIONED_CHANGE.value and r.get("state") == "differs"
                and not r.get("advisory") and not r.get("pr_only") and _name_head(r.get("name")) in heads):
            r["advisory"], r["linked_by"], r["note"] = True, "dangling_cover", DANGLING_NOTE


def _name_head(name) -> str:
    """The first part of an observation name or cover, lower case: "C1.x" -> "c1", "c1_x" -> "c1". Empty when that
    part holds a wildcard, so a bare "*" or "c*" never links."""
    head = re.split(r"[._]", str(name or ""), maxsplit=1)[0].lower()
    return "" if any(ch in head for ch in "*?[") else head


SHAPE_NOTE = "probably the claimed change, check"


_EXC_NAME_RE = re.compile(r"^[A-Za-z_][\w.]*(?:Error|Exception)$")


def _exc_of(value) -> str | None:
    """The exception type of an observation value: {"raises": "Name"} or a bare "NameError" string."""
    if isinstance(value, str):
        return value if _EXC_NAME_RE.match(value) else None
    return _exception_name(value)


def _shape(res: dict) -> str | None:
    """The exception name when main raised and the PR returned a value (not an exception), else None.

    A sibling pair that splits the same change across two observations (main raises and the pull request is
    absent on one, main is absent and the pull request returns a value on the other) carries that exception on
    ``split_shape``. It is the same shape as one observation with both sides."""
    split = res.get("split_shape")
    if isinstance(split, str) and split:
        return split
    exc = _exc_of(res.get("main"))
    if res.get("state") != "differs" or not exc or _exc_of(res.get("pr")) or res.get("pr") == ABSENT:
        return None
    return exc


_OBS_PREFIX = re.compile(r"^([A-Za-z]{1,8}\d+)[._]")
SPLIT_SHAPE_NOTE = "main raised and the pull request returned a value, split across two observations"


def _obs_prefix(name) -> str | None:
    """The claim id at the start of an observation name: ``c1_exception`` and ``c1.result`` are both ``c1``."""
    m = _OBS_PREFIX.match(str(name or ""))
    return m.group(1).lower() if m else None


def _raise_half(res: dict) -> str | None:
    """The exception main raised when this observation has nothing on the pull request."""
    if res.get("state") != "differs" or res.get("pr_only") or res.get("pr") != ABSENT:
        return None
    return _exc_of(res.get("main"))


def _value_half(res: dict) -> bool:
    """True when main is absent and the pull request returned a value that is not an exception."""
    return (res.get("state") == "differs" and not res.get("pr_only") and res.get("main") == ABSENT
            and res.get("pr") != ABSENT and not _exc_of(res.get("pr")))


def split_raise_value(observations: list) -> dict[str, str]:
    """Observation name to exception, for a raise→value change recorded as two siblings.

    ``c1_exception`` (main ``IndexError``, pull request absent) together with ``c1_result`` (main absent, pull
    request a value) is one shape: main raised IndexError and the pull request returned a value. The two names
    share the claim-id prefix (``c1_`` or ``c1.``). A prefix with any other count of those halves is left alone,
    so two values are not paired with one exception by guesswork."""
    groups: dict[str, list] = {}
    for res in observations or []:
        if not isinstance(res, dict):
            continue
        prefix = _obs_prefix(res.get("name"))
        if prefix and isinstance(res.get("name"), str):
            groups.setdefault(prefix, []).append(res)
    out: dict[str, str] = {}
    for group in groups.values():
        raised = [(res, exc) for res in group if (exc := _raise_half(res))]
        values = [res for res in group if _value_half(res)]
        if len(raised) != 1 or len(values) != 1:
            continue
        exc = raised[0][1]
        out[raised[0][0]["name"]] = exc
        out[values[0]["name"]] = exc
    return out


def _link_split_raise_value(spec: dict, out: list[dict]) -> None:
    """Give a split raise→value pair the shape of one observation, and link it to the claim its names name.

    The claim id is the shared prefix (``c1_exception`` links claim C1) when that claim expects a difference.
    The two observations are then that claim, not two unclaimed differences. A pair whose prefix is not a
    differs claim on this probe keeps the shape (so a title claim can still cover it) and stays unclaimed here."""
    shapes = split_raise_value(out)
    if not shapes:
        return
    by_id = {str(c.get("id") or "").lower(): c for c in spec.get("claims") or [] if isinstance(c, dict)}
    for res in out:
        exc = shapes.get(res.get("name"))
        if not exc:
            continue
        res["split_shape"] = exc
        claim = by_id.get(_obs_prefix(res.get("name")) or "")
        if not claim or claim.get("expect") != "differs" or res.get("pr_only") or res.get("state") != "differs":
            continue
        if res.get("label") != FindingLabel.UNMENTIONED_CHANGE.value:
            continue
        res.pop("advisory", None)
        res["claim"] = claim["id"]
        res["label"] = FindingLabel.PROVEN.value
        res["linked_by"] = "shape"
        res["note"] = SPLIT_SHAPE_NOTE


# "Don't raise IndexError ..." in a pull-request title. The name has to look like an exception type.
_DONT_RAISE = re.compile(
    r"(?i)\b(?:don['’]t|do\s+not|does\s+not|doesn['’]t|should\s+not|shouldn['’]t|must\s+not|never)\s+raise\b")
_EXC_WORD = re.compile(r"\b([A-Za-z_]\w*(?:Error|Exception|Failure))\b")


def dont_raise_names(title: str) -> list[str]:
    """Exception names a title says the code should not raise, in order, short form (``pkg.IndexError`` -> IndexError)."""
    out = []
    for m in _DONT_RAISE.finditer(title or ""):
        window = re.split(r"[.!?]", (title or "")[m.end():m.end() + 80], maxsplit=1)[0]
        for name in _EXC_WORD.findall(window):
            short = name.split(".")[-1]
            if short not in out:
                out.append(short)
    return out


def apply_title_claim(probe_results: dict | None, title: str) -> dict | None:
    """Count the pull-request title as a claim.

    "Don't raise X" covers any unclaimed difference where main raises X and the PR returns a value, including
    when that change is split across two sibling observations (one raises on main, the other returns the value
    on the pull request). Those observations are re-judged as proven by a claim whose id is ``title``. Anything
    else is left as it was."""
    names = dont_raise_names(title)
    if not probe_results or not names:
        return probe_results
    items = []
    for it in probe_results.get("items") or []:
        if not isinstance(it, dict):
            items.append(it)
            continue
        # A split pair (raise on one name, value on its sibling) is the same shape as one observation that
        # has both sides. Rule 55 covers those names too.
        paired = split_raise_value(it.get("observations") or [])
        covered = [o.get("name") for o in it.get("observations") or []
                   if isinstance(o, dict) and o.get("label") == FindingLabel.UNMENTIONED_CHANGE.value
                   and not o.get("advisory") and o.get("name")
                   and (_shape(o) in names or paired.get(o.get("name")) in names)]
        if not covered or not it.get("runs"):
            items.append(it)
            continue
        claims = [c for c in it.get("claims") or [] if not (isinstance(c, dict) and c.get("id") == "title")]
        claims.append({"id": "title", "text": title, "expect": "differs", "source": "PR title", "covers": covered})
        items.append(rejudge_entry(dict(it, claims=claims)))
    return dict(probe_results, items=items)


def _shape_link(out: list[dict]) -> None:
    """Fix 49: an unclaimed difference with the same shape as a proven claimed sibling in the same probe (the same
    main exception type turning into a value on the PR) is advisory, "probably the claimed change, check". It stays
    unmentioned_change and visible; it just no longer raises attention on its own."""
    proven = {_shape(r) for r in out if r.get("label") == FindingLabel.PROVEN.value and r.get("claim")} - {None}
    for r in out:
        if (r.get("label") == FindingLabel.UNMENTIONED_CHANGE.value and not r.get("advisory")
                and not r.get("pr_only") and _shape(r) in proven):
            r["advisory"], r["linked_by"], r["note"] = True, "shape", SHAPE_NOTE


SIBLING_NOTE = "the same difference is proven by a claim in another probe, check"


def _value_key(r: dict) -> tuple:
    return (r.get("name"), json.dumps(r.get("main"), sort_keys=True, default=str),
            json.dumps(r.get("pr"), sort_keys=True, default=str))


def _all_runs(it: dict, name: str) -> str:
    runs = it.get("runs") or {}
    return json.dumps({side: [o.get(name, "<absent>") if isinstance(o, dict) else None for o in runs.get(side) or []]
                       for side in ("main", "pr")}, sort_keys=True, default=str)


def _exact_cover(claims: list, cid, name: str) -> bool:
    """The claim names this observation exactly: a cover pattern equal to the name, with no wildcard."""
    return any(isinstance(c, dict) and c.get("id") == cid and name in [p for p in c.get("covers") or []
                                                                         if isinstance(p, str) and not any(
                                                                             ch in p for ch in "*?[")]
               for c in claims or [])


def link_across_probes(items: list[dict]) -> list[dict]:
    """Probes of one PR often print each other's observations. An unclaimed difference, or one that contradicts a
    "same" claim, is advisory ("the same difference is proven by a claim in another probe, check") when another
    probe of the same PR proves it for a claimed difference, and both of these hold:
    - it is the same check: the same name with the same recorded values in every run on both sides, and
    - the proving claim names it exactly (a cover with no wildcard).
    A proving result that is itself advisory or unstable only on the PR never links. Differences unstable only on the
    PR are never linked. It caps the verdict at could_not_verify instead of raising attention. Returns new items;
    the input is not changed."""
    proven: dict = {}
    for it in items:
        for r in it.get("observations") or []:
            if (r.get("label") == FindingLabel.PROVEN.value and r.get("state") == "differs" and r.get("claim")
                    and not r.get("advisory") and not r.get("pr_only")
                    and _exact_cover(it.get("claims"), r.get("claim"), r.get("name"))):
                key = (_value_key(r), _all_runs(it, r.get("name")))
                proven.setdefault(key, set()).add(it.get("id"))
    if not proven:
        return items
    out = []
    for it in items:
        obs = []
        for r in it.get("observations") or []:
            if (r.get("label") in (FindingLabel.UNMENTIONED_CHANGE.value, FindingLabel.FALSE_CLAIM.value)
                    and r.get("state") == "differs" and not r.get("advisory") and not r.get("pr_only")
                    and proven.get((_value_key(r), _all_runs(it, r.get("name"))), set()) - {it.get("id")}):
                r = dict(r, advisory=True, linked_by="sibling", note=SIBLING_NOTE)
            obs.append(r)
        out.append(dict(it, observations=obs))
    return out


def run_once(path: Path, python: Path, cwd: Path, env: dict, timeout: int, launch=None,
             literal_output: bool = False) -> tuple[dict, str, float]:
    """launch(argv, env, cwd) -> (argv, env, cwd) wraps the command, e.g. into the sandbox (guardrails/sandbox.py)."""
    t0 = time.time()
    argv = [str(python), str(path)]
    if launch:
        argv, env, cwd = launch(argv, env, cwd)
    with tempfile.TemporaryFile() as fo, tempfile.TemporaryFile() as fe:
        try:
            cp = subprocess.run(argv, cwd=cwd, env=env, stdout=fo, stderr=fe, timeout=timeout,
                                start_new_session=True, preexec_fn=_limit_files)
            code = cp.returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
        out, err = _head(fo, MAX_OUTPUT_BYTES + 1), _head(fe, 8000)
    if code == "timeout":
        return observations_of("", code), f"timed out after {timeout}s", round(time.time() - t0, 1)
    log = out[-4000:] + ("\n--- stderr ---\n" + err[-4000:] if err else "")
    return observations_of(out, code, literal_output), log, round(time.time() - t0, 1)


FILE_LIMIT_BYTES = 64_000_000   # RLIMIT_FSIZE of a probe: caps its stdout/stderr files and anything it writes


def _limit_files():
    resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_LIMIT_BYTES, FILE_LIMIT_BYTES))


def _head(f, n: int) -> str:
    f.seek(0)
    return f.read(n).decode(errors="replace")


def run_probe(path: Path, pythons: dict, outdir: Path, cwd: Path | dict, envs: dict, runs: int = 3,
              source: str = "library", launchers: dict | None = None, guard=None, literal_output: bool = False) -> dict:
    """Run one probe file `runs` times per side, alternating main/PR; save outputs; judge. Returns the record entry.
    envs: {"main": env, "pr": env}, each side's own allowlisted environment (guardrails.isolation.untrusted_env).
    guard(path) is called before every PR-side run and raises (poc.freeze.FreezeError) to stop it."""
    spec = read_spec(path)
    cwds = cwd if isinstance(cwd, dict) else {"main": cwd, "pr": cwd}
    for c in cwds.values():
        c.mkdir(parents=True, exist_ok=True)
    got: dict = {"main": [], "pr": []}
    files: dict = {"main": [], "pr": []}
    per_run = []
    for i in range(1, runs + 1):
        for side in ("main", "pr"):
            if side == "pr" and guard:
                guard(path)
            obs, log, secs = run_once(path, pythons[side], cwds[side], envs[side], int(spec["timeout_s"]),
                                         (launchers or {}).get(side), literal_output)
            fname = f"probe-{spec['id']}-{side}-{i}.jsonl"
            write_output(outdir / fname, obs)
            (outdir / f"probe-{spec['id']}-{side}-{i}.log").write_text(log)
            got[side].append(obs)
            files[side].append(fname)
            per_run.append({"side": side, "run": i, "seconds": secs, "ok": PROBE_ERROR not in obs})
    return entry(spec, got, files, per_run, source, path)


def entry(spec: dict, got: dict, files: dict, per_run: list, source: str, path: Path | str | None) -> dict:
    results = judge(dict(spec, source=source), got, files)
    return {"id": spec["id"], "source": source, "path": str(path) if path else None, "sha256": spec.get("sha256"),
            "target": spec["target"], "about": spec["about"], "claims": spec.get("claims", []),
            "runs_per_side": len(got["main"]), "per_run": per_run, "outputs": files, "runs": got,
            "observations": results}


def rejudge_entry(item: dict) -> dict:
    """Recompute an entry's observations from its recorded runs (no files, no environments needed)."""
    spec = {"id": item["id"], "target": item["target"], "about": item["about"], "claims": item.get("claims", []),
            "source": item.get("source")}
    return dict(item, observations=judge(spec, item["runs"], item.get("outputs")))


def _exception_name(value) -> str | None:
    """The exception type when a probe observation is only ``{"raises": "Name"}``."""
    if isinstance(value, dict) and set(value) == {"raises"} and isinstance(value.get("raises"), str):
        return value["raises"]
    return None


def _no_type_aware_input(value) -> bool:
    return isinstance(value, dict) and value.get("skipped") == "no type-aware input"


def classify_item(item: dict) -> dict:
    """Mark a probe uninformative or not_run.

    uninformative: every observation is the same exception type on both sides (for example AttributeError on every
    input). That probe did not observe the function, so it must not count as ran or as adequate.
    not_run: every observation says no type-aware input could be built, so the probe did not call the function.
    """
    obs = item.get("observations") or []
    out = dict(item)
    if not obs:
        out["status"] = "error"
        _downgrade_coverage(out, "the probe produced no observations; not counted as ran or adequate", zero=True)
        return out
    why = crash_reason(item)
    if why:
        out["status"] = "crashed"
        out["uninformative_reason"] = why
        _downgrade_coverage(out, why + "; not counted as ran or adequate", zero=True)
        return out
    if all(_no_type_aware_input(o.get("main")) and _no_type_aware_input(o.get("pr")) for o in obs):
        reason = "no type-aware input could be built, so the probe did not run"
        out["status"] = "not_run"
        out["uninformative_reason"] = reason
        _downgrade_coverage(out, reason, zero=True)
        return out
    if all(o.get("probe_broken") for o in obs):
        reason = "uninformative: every observation is probe-broken (the same exception or skip value on both sides)"
        out["status"] = "uninformative"
        out["uninformative_reason"] = reason
        _downgrade_coverage(out, reason + "; not counted as ran or adequate", zero=True)
        return out
    names = []
    for o in obs:
        if o.get("state") != "same":
            return _counted_or_rejected(out)
        main_exc, pr_exc = _exception_name(o.get("main")), _exception_name(o.get("pr"))
        if not main_exc or main_exc != pr_exc:
            return _counted_or_rejected(out)
        names.append(main_exc)
    if len(set(names)) != 1:
        return _counted_or_rejected(out)
    reason = f"uninformative: every input raised {names[0]} on both sides"
    out["status"] = "uninformative"
    out["uninformative_reason"] = reason
    _downgrade_coverage(out, reason + "; not counted as ran or adequate", zero=True)
    return out


def crash_reason(item: dict) -> str | None:
    """Why a probe's runs give no usable evidence, or None. A probe crashed when every main-side run ended in
    PROBE_ERROR (an exception, non-JSON output, a timeout or a non-zero exit). Coverage is measured on the main side,
    so lines it touched there before failing say nothing about the change and must not count. A probe that works on
    main but crashes on the PR side is a finding, not a crash of the probe, and is left alone."""
    rs = (item.get("runs") or {}).get("main") or []
    if rs and all(isinstance(o, dict) and PROBE_ERROR in o for o in rs):
        return "the probe crashed or printed no parsed output on every main-side run"
    return None


def _downgrade_coverage(item: dict, note: str, zero: bool = False) -> None:
    """A probe that did not observe the change is not adequate, even if a line counter moved. zero=True also stops
    its touched lines counting as covered (the raw count is kept as changed_lines_touched)."""
    cov = item.get("probe_changed_line_coverage")
    if not isinstance(cov, dict):
        cov = {"status": "not measured", "why": note}
    cov = dict(cov)
    cov["adequacy"] = "not_adequate"
    cov["note"] = note
    if zero and cov.get("changed_lines_covered"):
        cov["changed_lines_touched"] = cov["changed_lines_covered"]
        cov["changed_lines_covered"] = 0
    item["probe_changed_line_coverage"] = cov


def apply_status(probe_results: dict | None) -> dict | None:
    """Set each item's status and the overall status. Overall is uninformative only when every item is."""
    if not probe_results or not probe_results.get("items"):
        return probe_results
    items = link_across_probes([classify_item(it) for it in probe_results["items"]])
    statuses = [it.get("status") for it in items]
    if any(s == "ran" for s in statuses):
        status = "ran"
    elif statuses and all(s == "rejected" for s in statuses):
        status = "rejected"
    elif statuses and all(s == "uninformative" for s in statuses):
        status = "uninformative"
    elif statuses and all(s == "not_run" for s in statuses):
        status = "none"
    elif statuses and all(s in ("error", "crashed") for s in statuses):
        status = "error"
    else:
        status = "ran"
    summary = summarize([it for it in items if it.get("status") == "ran"])
    notes = [it["uninformative_reason"] for it in items if it.get("uninformative_reason")]
    notes += [it["rejected_reason"] for it in items if it.get("rejected_reason")]
    if notes:
        summary = dict(summary, reason="; ".join([summary["reason"]] * bool(summary["reason"]) + notes))
    return dict(probe_results, items=items, status=status, summary=summary)


def is_warning_observation(name: str) -> bool:
    """An observation about warnings (its name mentions a warning), e.g. 'x.warning_raised', 'warnings.count'."""
    return "warn" in str(name).lower()


def _input_of(name: str) -> str | None:
    """The input an observation belongs to: its dotted name without the last part ("c2.case1.rel" -> "c2.case1").
    None for an undotted name, whose input cannot be told apart."""
    name = str(name)
    return name.rsplit(".", 1)[0] if "." in name else None


def _agreeing_differs_when_proven(obs: list[dict]) -> list[dict]:
    """Covered observations of a differs claim that all agree, once another differs claim is proven.

    Each one is labelled needs_human with state "same" ("does not differ although the claim says it does").
    They are advisory: the claim was not shown on these inputs, and a related change was proven. Returned in
    observation order. A claim with any other covered observation (a difference, a contradiction, a flaky or
    unstable result, or a probe that did not run) is not this case. Nothing is returned when no differs claim
    is proven, or when the only proof is a claim that the result stays the same."""
    proven = {o.get("claim") for o in obs
              if o.get("claim") and o.get("label") == FindingLabel.PROVEN.value and o.get("state") == "differs"
              and not o.get("advisory") and not o.get("pr_only")}
    if not proven:
        return []
    groups: dict[str, list[dict]] = {}
    for o in obs:
        cid = o.get("claim")
        if cid:
            groups.setdefault(cid, []).append(o)
    out = []
    for cid, group in groups.items():
        if cid in proven or not group:
            continue
        if all(o.get("state") == "same" and o.get("label") == FindingLabel.NEEDS_HUMAN.value
               and not o.get("advisory") and not o.get("pr_only") for o in group):
            out.extend(group)
    return out


def summarize(items: list[dict]) -> dict:
    """Findings over all probes of a PR: labels, red/amber observations, proven claims, reason text."""
    obs = [o | {"probe": it["id"]} for it in items for o in it["observations"]]
    labels = [FindingLabel(o["label"]) for o in obs]
    raw_flagged = [o for o in obs if COLOUR.get(FindingLabel(o["label"])) in ("red", "amber")]
    # Noise filter: an observation that changes between runs of the SAME side is noise, not a finding; it is listed
    # but never decides the verdict. A difference that is only about warnings never counts as a break on its own.
    pr_only_noisy = [o for o in obs if o.get("pr_only") == "noisy"]
    noisy = [o for o in raw_flagged if o["label"] == FindingLabel.FLAKY.value and o.get("pr_only") != "noisy"]
    # Flaky on one side is noise. Unstable only on the pull request is not, even when it is too mixed to call.
    # "advisory" is only ever set by the product route (poc/claim_hygiene.py) on a model probe with no linked claim.
    advisory = [o for o in raw_flagged if o.get("advisory")]
    # General rule for any claim that says something changes, checked per input: when one input reports several
    # values ("case1.title", "case1.rel") and at least one of them differs as claimed, the claim is met for that
    # input, and its other values that rightly stayed the same are advisory only. An input on which no value of the
    # claim differs still needs attention. Inputs are told apart only by a dotted observation name.
    met = {(o["claim"], _input_of(o["name"])) for o in obs if o.get("claim") and _input_of(o["name"])
           and o["label"] == FindingLabel.PROVEN.value and o.get("state") == "differs"}
    unchanged_sub = [o for o in raw_flagged if o["label"] == FindingLabel.NEEDS_HUMAN.value and o.get("state") == "same"
                     and not o.get("advisory") and (o.get("claim"), _input_of(o["name"])) in met]
    # A whole differs claim that was not shown (every covered observation agrees) is advisory when some other
    # differs claim on this record is already proven. It does not raise needs attention. A claim that is only
    # partly shown, or a record with nothing proven, is unchanged.
    unshown = _agreeing_differs_when_proven(obs)
    flagged = [o for o in raw_flagged
               if o["label"] != FindingLabel.FLAKY.value and o.get("pr_only") != "noisy" and not o.get("advisory")
               and o not in unchanged_sub and o not in unshown]
    warning_only = [o for o in flagged if is_warning_observation(o["name"])]
    if flagged and len(warning_only) == len(flagged):
        flagged = []
    else:
        warning_only = []
    proven = sorted({o["claim"] for o in obs if o["label"] == FindingLabel.PROVEN.value})
    bits = []
    if flagged:
        names = {FindingLabel.UNMENTIONED_CHANGE.value: "differs and no claim covers it",
                 FindingLabel.FALSE_CLAIM.value: "differs although the claim says it does not",
                 FindingLabel.NEEDS_HUMAN.value: "does not differ although the claim says it does",
                 FindingLabel.FLAKY.value: "gives different results between runs of the same side",
                 FindingLabel.UNSTABLE_ON_PR.value: "is stable on the base and unstable only on the pull request"}
        bits.append(f"probe: {len(flagged)} observation(s) need attention: "
                    + "; ".join(f"{o['name']} {names[o['label']]}" + (f" ({o['claim']})" if o.get("claim") else "")
                                for o in flagged[:4]))
    if noisy:
        bits.append(f"probe: {len(noisy)} observation(s) ignored as noise (they change between runs of the same "
                    "side)")
    if pr_only_noisy:
        bits.append(f"probe: {len(pr_only_noisy)} observation(s) stable on the base and unstable only on the PR, "
                    "too mixed to call")
    if warning_only:
        bits.append(f"probe: {len(warning_only)} warning-only difference(s) not counted on their own")
    if advisory:
        # A probe that links claims can still carry advisory differences (a mark kept from the run that wrote the
        # record, or a link by id, shape or sibling). Name those differences rather than say it has no linked claims.
        linked = {it["id"] for it in items if it.get("claims")}
        bare = [o for o in advisory if o["probe"] not in linked]
        named = [o for o in advisory if o["probe"] in linked]
        if bare:
            bits.append(f"probe: {len(bare)} difference(s) from a probe with no linked claims shown as advisory only")
        if named:
            bits.append(f"probe: {len(named)} difference(s) no linked claim covers, shown as advisory only: "
                        + ", ".join(o["name"] for o in named[:4]) + (f" (+{len(named) - 4} more)" if len(named) > 4
                                                                     else ""))
    if unchanged_sub:
        bits.append(f"probe: {len(unchanged_sub)} unchanged sub-check(s) of an input where the claim's change was seen, shown as "
                    "advisory only: " + "; ".join(f"{o['name']} ({o['claim']})" for o in unchanged_sub[:4]))
    if unshown:
        more = f" (+{len(unshown) - 4} more)" if len(unshown) > 4 else ""
        bits.append(f"probe: {len(unshown)} observation(s) shown as advisory only "
                    "(claim not shown on these inputs; a related change was proven): "
                    + "; ".join(f"{o['name']} ({o['claim']})" for o in unshown[:4]) + more)
    if proven:
        bits.append(f"probe: claim(s) {', '.join(proven)} proven")
    same = sum(1 for o in obs if o["label"] == FindingLabel.NO_DIFFERENCE.value)
    if same:
        bits.append(f"probe: {same} other observation(s) identical on both sides")
    errors = [o for o in obs if o["label"] == FindingLabel.NOT_TESTABLE.value]
    if errors:
        bits.append(f"probe: {len(errors)} probe(s) could not run on either side")
    return {"labels": [x.value for x in labels], "flagged": [{k: o[k] for k in ("probe", "name", "label", "claim")}
                                                             for o in flagged],
            "proven_claims": proven, "reason": "; ".join(bits),
            "ignored_noise": [o["name"] for o in noisy], "ignored_warning_only": [o["name"] for o in warning_only],
            "pr_only_noisy": [o["name"] for o in pr_only_noisy],
            "advisory_unchanged_subchecks": [o["name"] for o in unchanged_sub],
            "advisory_agreeing_differs": [o["name"] for o in unshown]}


ONE_SIDE_NOTE = "the claim describes the old behaviour only (before the fix), check"
# The single shape "Before the fix, X raises/returns Y": one sentence about the old behaviour only, anchored at both
# ends. A second clause (and, but, while, whereas, after, a comma, semicolon or second sentence) is not this shape.
_ONE_SIDE_RE = re.compile(r"^\s*before\s+(?:the|this)\s+(?:fix|change|patch|pr|pull request)\s*,?\s+"
                          r"(?:(?!\b(?:and|but|while|whereas|after|afterwards|then|also|too)\b)[^,;.!?])+?"
                          r"\b(?:raises?|raised|returns?|returned)\b"
                          r"(?:(?!\b(?:and|but|while|whereas|after|afterwards|then|also|too)\b)(?:[^,;.!?]|\.(?=\S)))*?"
                          r"\.?\s*$", re.I)
# Words that make a claim about keeping behaviour or about both sides, where a difference is a real contradiction.
# A second sentence is never allowed: only a dot inside a value ("1.5", "a.b") may appear before the end.
_KEEP_RE = re.compile(r"\b(?:preserv\w*|still|unchanged|as before|continu\w*|existing|keeps?|retains?|same|"
                      r"regress\w*|break\w*|no longer|identical\w*|equal\w*|alter\w*|both|either|each|"
                      r"all|any|regardless|versions?)\b", re.I)


def is_one_side_claim(claim: dict | None) -> bool:
    """True for a "same" claim that only states what one side does, with no wording about keeping behaviour."""
    from poc.claim_hygiene import says_stays_same
    text = str((claim or {}).get("text") or "")
    return (bool(claim) and claim.get("expect") == "same" and bool(_ONE_SIDE_RE.search(text))
            and not _KEEP_RE.search(text) and not says_stays_same(text))


def _one_side_claim_link(spec: dict, out: list[dict]) -> None:
    """A difference against a "same" claim that describes one side only (is_one_side_claim) is advisory, not a
    contradiction. It caps the verdict at could_not_verify. Differences unstable only on the PR are never linked."""
    claims = {c.get("id"): c for c in spec.get("claims") or [] if isinstance(c, dict)}
    for r in out:
        if (r.get("label") == FindingLabel.FALSE_CLAIM.value and r.get("state") == "differs" and not r.get("advisory")
                and not r.get("pr_only") and is_one_side_claim(claims.get(r.get("claim")))):
            r["advisory"], r["linked_by"], r["note"] = True, "one_side_claim", ONE_SIDE_NOTE
