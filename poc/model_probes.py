"""Model-written probes: claims from the PR text, probe code from the claims and BASE-side code, then frozen.

    generate(provider, repo, pr, title, body, base_files, base_root, pr_roots, outdir) -> dict

1. Inputs: the PR title and description, and base-side files only (`poc.freeze.base_inputs` rejects PR-side paths).
2. Claims (structured JSON, CLAIMS_SCHEMA): each claim must quote the PR text exactly (`source_quote`); claims whose
   quote is not found are rejected, untestable ones are kept in the record but get no probe.
3. Probes (structured JSON, PROBES_SCHEMA): each probe's code is validated (size cap, parses, no PROBE of its own,
   claim ids known, observation patterns given) and written as a probe file with a generated literal PROBE dict.
4. Each file is frozen (`poc.freeze.freeze`) before any PR-side execution.

Model code is untrusted. It runs like every probe: inside the side's sandbox without network, with the probe timeout
capped at MODEL_TIMEOUT_S, and with the output size and contract checks of poc/probes.py.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from poc import freeze
from poc.model_provider import CLAIMS_PROMPT, CLAIMS_SCHEMA, PROBES_PROMPT, PROBES_SCHEMA, Provider, ProviderError

MAX_CODE_CHARS = 20_000
MAX_PROBES = 4
MAX_CONTEXT_CHARS = 60_000
MODEL_TIMEOUT_S = 60
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
# The probe contract says the last printed line is a JSON object, so every probe needs the json module. Models
# sometimes call json.dumps without importing it, and then the probe fails the same way on both sides and tests
# nothing. The harness adds the import itself; it changes no behaviour of the code under test.
JSON_IMPORT = "import json  # added by the harness: the observations line is printed as JSON\n"
# Product checks only (the study route keeps PROBES_PROMPT exactly as it is). Generic rules, no project names.
PROBE_SAFETY_RULES = """
Extra rules for every probe:
- Never monkeypatch, mock or replace standard-library or runtime core functions (time and clock functions, asyncio
  event-loop internals, random, os, sys) with finite fakes, lists or iterators; they run out and crash the probe.
- Never build hand-made fake objects: no mocks, stubs, MagicMock or stand-in classes in place of the project's own
  objects. Call the project's real code with real inputs.
- Prefer calling the real public API with small, real inputs.
- If a value really must be controlled, use a deterministic function with no limit (for example a counter that keeps
  counting), never a fixed list of values.
- Keep each probe simple and always print the parsed observations line, even when a call fails."""
PRODUCT_PROBES_PROMPT = PROBES_PROMPT + "\n" + PROBE_SAFETY_RULES
# A probe rewrite sees only the probe's own source and its own error text: never either side's observations.
REPAIR_PROMPT = PRODUCT_PROBES_PROMPT + """
You are now repairing ONE probe that crashed in its own code on both sides, before reaching the code under test. You
get only its source and its error text. Return the same probe (same id, about and claims) with corrected code that
follows every rule above. Answer with JSON only."""
MAX_PROBE_REWRITES = 2   # first attempt plus up to 2 rewrites: 3 attempts in total
UNLINKED_REASON = ("no probe listed the claim ids it checks, so its results could not be tied to any claim; in each "
                   "probe, \"claims\" must name the claim ids it checks and the observation names that cover them")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def grounded_claims(raw: dict, title: str, body: str | None) -> tuple[list, list]:
    """(kept, rejected): a claim is kept only if its source_quote is found in the title or description."""
    text = _norm(title) + " \n " + _norm(body)
    kept, rejected = [], []
    for c in (raw or {}).get("claims", [])[:20]:
        q = _norm(c.get("source_quote", ""))
        ok = bool(q) and q in text and c.get("expect") in ("same", "differs") and c.get("id")
        (kept if ok else rejected).append(c | ({} if ok else {"rejected": "source_quote not found in the PR text"}))
    return kept, rejected


def _unescape_code(code):
    """Some replies double-escape the script, so it arrives as ONE line with literal backslash-n sequences. If it
    does not parse as is but parses after turning those into real line breaks, use the unescaped version."""
    if not isinstance(code, str) or "\n" in code or "\\n" not in code:
        return code
    try:
        ast.parse(code)
        return code
    except SyntaxError:
        pass
    fixed = code.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
    try:
        ast.parse(fixed)
        return fixed
    except SyntaxError:
        return code


def _tidy_id(x):
    """'P1' -> 'p1', 'probe_get_x' -> 'probe-get-x'; non-strings are returned unchanged (and then rejected)."""
    if not isinstance(x, str):
        return x
    return re.sub(r"[^a-z0-9-]+", "-", x.lower()).strip("-")[:40] or x


EMPTY_PROBE = "empty probe: the code has no test statements (only imports, comments or a docstring)"


def has_test_code(tree: ast.AST) -> bool:
    """True when the module does something beyond imports, docstrings, `pass` and `...`."""
    for stmt in getattr(tree, "body", []):
        if isinstance(stmt, (ast.Import, ast.ImportFrom, ast.Pass)):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue
        return True
    return False


def validate_probe(p: dict, claim_ids: set) -> str | None:
    """None if the model's probe is acceptable, else why not."""
    if not ID_RE.match(str(p.get("id", ""))):
        return f"bad probe id {p.get('id')!r}"
    code = p.get("code") or ""
    if len(code) > MAX_CODE_CHARS:
        return f"code too long ({len(code)} chars > {MAX_CODE_CHARS})"
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"code does not parse: {e.msg} (line {e.lineno})"
    if not has_test_code(tree):
        return EMPTY_PROBE
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PROBE" for t in node.targets):
            return "code defines PROBE itself"
    for c in p.get("claims", []):
        if c.get("id") not in claim_ids:
            return f"probe claim {c.get('id')!r} is not one of the extracted claims"
        if not c.get("covers") or not all(isinstance(x, str) and x for x in c["covers"]):
            return f"claim {c.get('id')} covers no observation"
    return None


def probe_file(p: dict, target: str, claims_by_id: dict, gen_label: str) -> str:
    spec = {"id": f"model-{p['id']}", "target": target, "about": p.get("about", "")[:300],
            "claims": [{"id": c["id"], "source": "PR description", "text": claims_by_id[c["id"]]["text"],
                        "covers": list(c["covers"]), "expect": c["expect"]} for c in p.get("claims", [])],
            "timeout_s": MODEL_TIMEOUT_S, "generator": gen_label}
    return (f'"""Model-written probe for {target} ({gen_label}). Generated from the PR text and base-side code only;\n'
            'frozen before any PR-side execution. Untrusted: runs only in the sandbox without network."""\n'
            f"PROBE = {spec!r}\n\n" + JSON_IMPORT + p["code"].rstrip() + "\n")


def _context(base_files: dict) -> str:
    parts, used = [], 0
    for rel, path in sorted(base_files.items()):
        try:
            txt = Path(path).read_text(errors="replace")
        except OSError:
            continue
        txt = txt[: max(0, MAX_CONTEXT_CHARS - used)]
        used += len(txt)
        parts.append(f"### BASE-side file {rel}\n{txt}")
        if used >= MAX_CONTEXT_CHARS:
            break
    return "\n\n".join(parts)


def _usable(resp, claim_ids: set) -> list:
    """The probes of a reply that pass validate_probe (after tidying ids and unescaping code)."""
    return [p for p in (resp or {}).get("probes", [])[:MAX_PROBES] if isinstance(p, dict)
            and not validate_probe(dict(p, id=_tidy_id(p.get("id")), code=_unescape_code(p.get("code"))), claim_ids)]


def generate(provider: Provider, repo: str, pr: int, title: str, body: str | None, base_files: dict,
             base_root: Path, pr_roots: list, outdir: Path, product: bool = False) -> dict:
    """product=True (product checks only) adds PROBE_SAFETY_RULES; the study route passes nothing and is unchanged."""
    from poc import run_progress
    PROBES_PROMPT = PRODUCT_PROBES_PROMPT if product else globals()["PROBES_PROMPT"]

    inputs = freeze.base_inputs(title, body, base_files, base_root, pr_roots)   # raises on PR-side input paths
    ctx = {"repo": repo, "pr": pr}
    out: dict = {"provider": provider.describe(), "claims": [], "rejected_claims": [], "probes": [], "errors": []}
    pr_text = f"Title: {title}\n\nDescription:\n{body or ''}"
    run_progress.emit("claims", "super", "Super is extracting behaviour claims")
    try:
        raw = provider.complete_json("claims", CLAIMS_PROMPT, pr_text, CLAIMS_SCHEMA, ctx)
    except ProviderError as e:
        out["errors"].append(str(e))
        return out
    kept, rejected = grounded_claims(raw, title, body)
    out["claims"], out["rejected_claims"] = kept, rejected
    testable = [c for c in kept if c.get("testable")]
    if not testable and not base_files:
        return out
    if testable:
        user = (pr_text + "\n\nClaims:\n" + json.dumps(testable, indent=1) + "\n\n" + _context(base_files))
    else:
        # The PR changes source files but its text gave no testable claim: still ask for at least one probe that
        # records the behaviour of the functions in those files (no claims; plain code compares the outputs).
        out["no_claims_probe"] = True
        user = (pr_text + "\n\nClaims: none were testable. Still write at least one probe that calls the functions "
                "in the BASE-side files below with representative and edge-case inputs; give it an empty claims "
                "list.\n\n" + _context(base_files))
    run_progress.emit("probes", "super", "Super is writing behaviour probes")
    try:
        resp = provider.complete_json("probes", PROBES_PROMPT, user, PROBES_SCHEMA, ctx)
    except ProviderError as e:
        out["errors"].append(str(e))
        return out
    by_id = {c["id"]: c for c in testable}
    usable = _usable(resp, set(by_id))
    if not usable:
        # One retry, same gate and same BASE-side inputs: say why the first answer was unusable (generic reasons only)
        reasons = [validate_probe(dict(p, id=_tidy_id(p.get("id")), code=_unescape_code(p.get("code"))),
                                  set(by_id)) for p in
                   (resp or {}).get("probes", [])[:MAX_PROBES] if isinstance(p, dict)] or ["the probes list was empty"]
        out["retried"] = {"why": reasons[:5]}
        retry_user = (user + "\n\nYour previous answer contained no usable probe (" + "; ".join(map(str, reasons[:5]))
                      + "). Follow the coverage rule: write at least one probe per testable claim.")
        try:
            resp = provider.complete_json("probes", PROBES_PROMPT, retry_user, PROBES_SCHEMA, ctx)
        except ProviderError as e:
            out["errors"].append(f"retry: {e}")
    elif by_id and not any(p.get("claims") for p in usable):
        # Testable claims exist but no probe says which claim it checks. Its differences would then all look
        # unclaimed. Ask once more (same gate, same BASE-side inputs); keep the first answer unless the retry is
        # usable and links at least one claim, so no probe is lost.
        out["retried"] = {"why": [UNLINKED_REASON]}
        retry_user = (user + "\n\nYour previous answer had probes, but " + UNLINKED_REASON
                      + ". Follow the coverage rule: write at least one probe per testable claim.")
        try:
            again = provider.complete_json("probes", PROBES_PROMPT, retry_user, PROBES_SCHEMA, ctx)
        except ProviderError as e:
            out["errors"].append(f"retry: {e}")
        else:
            linked = [p for p in _usable(again, set(by_id)) if p.get("claims")]
            if linked:
                resp = again
            else:
                out["retried"]["kept_first_answer"] = "the retry linked no claim either"
    draft_probes: list = []
    for p in (resp or {}).get("probes", [])[:MAX_PROBES]:
        # Models name probes "P1" or "probe_x"; the id is only a file name, so normalise it rather than drop the probe
        if isinstance(p, dict) and isinstance(p.get("id"), str):
            p["id"] = _tidy_id(p["id"])
        if isinstance(p, dict):
            p["code"] = _unescape_code(p.get("code"))
            if not str(p.get("about") or "").strip():   # the probe runner requires a non-empty description
                p["about"] = "model-written probe of the changed files (no description given)"
        why = validate_probe(p, set(by_id))
        if why:
            out["errors"].append(f"probe {p.get('id')!r} rejected: {why}")
            continue
        draft_probes.append(p)

    # Console HITL: freeze only after the operator approves / adds scenarios.
    from poc import hitl
    if hitl.hitl_enabled():
        return hitl.gate_and_materialize(
            provider=provider, repo=repo, pr=pr, title=title, body=body,
            draft_probes=draft_probes, claims=kept, rejected_claims=rejected,
            base_files=base_files, base_root=base_root, pr_roots=pr_roots, outdir=outdir,
            tidy_id=_tidy_id, unescape_code=_unescape_code, validate_probe=validate_probe,
            probe_file=probe_file, errors=out["errors"],
        )

    gen = freeze.generator("model", model=provider.models["probes"], provider=provider.name)
    outdir.mkdir(parents=True, exist_ok=True)
    for p in draft_probes:
        path = outdir / f"model-{p['id']}.py"
        path.write_text(probe_file(p, f"{repo}#{pr}", by_id, gen["label"]))
        entry = {"path": path, "freeze": freeze.freeze(path, gen, inputs)}
        if product:
            entry["repair"] = {"draft": p, "target": f"{repo}#{pr}", "claims_by_id": by_id, "gen": gen,
                               "inputs": inputs, "ctx": ctx}
        out["probes"].append(entry)
    return out


_FRAME_RE = re.compile(r'^\s*File "([^"]+)", line \d+', re.M)


def _stdlib_file(f: str) -> bool:
    """A frame in the Python standard library (not site-packages, not a checkout). Frozen standard-library modules
    such as ``<frozen runpy>`` count too."""
    if re.fullmatch(r"<frozen [\w.]+>", f):
        return True
    return bool(re.search(r"/lib/python3\.\d+/", f)) and "site-packages" not in f and "dist-packages" not in f


# Python joins chained tracebacks with one of these lines; the last block is the error that ended the probe.
_CHAIN_RE = re.compile(r"^(?:During handling of the above exception, another exception occurred:|"
                       r"The above exception was the direct cause of the following exception:)\s*$", re.M)
# A fake value list given to a mock ran out: StopIteration raised from unittest/mock.py.
_MOCK_RAN_OUT_RE = re.compile(r'File "[^"]*/lib/python3\.\d+/unittest/mock\.py"[^\n]*\n(?:[^\n]*\n)?\s*StopIteration\b')


def _frames_own(block: str, probe_name: str) -> bool:
    frames = _FRAME_RE.findall(block or "")
    return bool(frames) and all(Path(f).name == probe_name or _stdlib_file(f) for f in frames)


def own_code_crash(log: str, probe_name: str) -> bool:
    """True when the log holds a traceback whose frames are only in the probe file itself or the standard library,
    i.e. it never reached the project's code (or any installed package). No traceback: False (not provable).

    One narrow exception for chained tracebacks: when the final block is a mock's fake value list running out
    (StopIteration from unittest/mock.py) and that final block stays in the probe and the standard library, the
    earlier blocks it was raised while handling are not counted. The probe's own fake broke the run either way.
    Any other chain is judged on every block, as before."""
    blocks = _CHAIN_RE.split(log or "")
    last = blocks[-1]
    if len(blocks) > 1 and _MOCK_RAN_OUT_RE.search(last) and _frames_own(last, probe_name):
        return True
    return _frames_own(log, probe_name)


def probe_broke_itself(item: dict, logs: dict, probe_name: str) -> bool:
    """A probe broke itself only if EVERY run crashed (no parsed output) on BOTH sides AND no traceback reaches the
    project's code. A crash on the PR side only, or one inside project code, is evidence and is never repaired."""
    from poc.probes import PROBE_ERROR
    runs = item.get("runs") or {}
    for side in ("main", "pr"):
        rs = runs.get(side) or []
        if not rs or not all(isinstance(o, dict) and PROBE_ERROR in o for o in rs):
            return False
        if not logs.get(side) or not all(own_code_crash(lg, probe_name) for lg in logs[side]):
            return False
    return True


def error_summary(logs: dict) -> str:
    """The probe's own error text (last traceback of the first main-side run), capped. No observations."""
    log = next(iter(logs.get("main") or []), "") or ""
    i = log.rfind("Traceback (most recent call last)")
    return (log[i:] if i >= 0 else log)[-3000:]


def plain_reason(err: str) -> str:
    if "StopIteration" in err and ("mock" in err or "side_effect" in err or "next(" in err):
        return "a fake value list ran out"
    last = [ln for ln in err.strip().splitlines() if ln.strip()][-1:] or ["unknown error"]
    return last[0].strip()[:120]


def rewrite_probe(provider: Provider, repair: dict, source: str, err: str) -> dict | None:
    """Ask the model to rewrite one probe from its own source and its own error text only. Returns the new draft
    (validated) or None."""
    user = ("Probe source:\n" + source + "\n\nIts error text:\n" + err)
    try:
        resp = provider.complete_json("probes", REPAIR_PROMPT, user, PROBES_SCHEMA, repair["ctx"])
    except ProviderError:
        return None
    old = repair["draft"]
    for p in (resp or {}).get("probes", [])[:1]:
        if not isinstance(p, dict):
            continue
        new = dict(old, code=_unescape_code(p.get("code")))
        if new["code"] == old.get("code") or validate_probe(new, set(repair["claims_by_id"])):
            return None
        return new
    return None
