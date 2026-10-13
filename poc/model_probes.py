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
            f"PROBE = {spec!r}\n\n" + p["code"].rstrip() + "\n")


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


def generate(provider: Provider, repo: str, pr: int, title: str, body: str | None, base_files: dict,
             base_root: Path, pr_roots: list, outdir: Path) -> dict:
    inputs = freeze.base_inputs(title, body, base_files, base_root, pr_roots)   # raises on PR-side input paths
    ctx = {"repo": repo, "pr": pr}
    out: dict = {"provider": provider.describe(), "claims": [], "rejected_claims": [], "probes": [], "errors": []}
    pr_text = f"Title: {title}\n\nDescription:\n{body or ''}"
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
    try:
        resp = provider.complete_json("probes", PROBES_PROMPT, user, PROBES_SCHEMA, ctx)
    except ProviderError as e:
        out["errors"].append(str(e))
        return out
    by_id = {c["id"]: c for c in testable}
    usable = [p for p in (resp or {}).get("probes", [])[:MAX_PROBES] if isinstance(p, dict)
              and not validate_probe(dict(p, id=_tidy_id(p.get("id")), code=_unescape_code(p.get("code"))),
                                     set(by_id))]
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
    gen = freeze.generator("model", model=provider.models["probes"], provider=provider.name)
    outdir.mkdir(parents=True, exist_ok=True)
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
        path = outdir / f"model-{p['id']}.py"
        path.write_text(probe_file(p, f"{repo}#{pr}", by_id, gen["label"]))
        out["probes"].append({"path": path, "freeze": freeze.freeze(path, gen, inputs)})
    return out
