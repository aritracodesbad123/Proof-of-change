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
# Product checks only: two extra rules for the probes prompt. Study runs keep PROBES_PROMPT exactly as it is.
PRODUCT_PROBE_RULES = (
    "\n\nImports: the package under test is installed on both sides. Import it by its installed import name, the "
    "way a user of the package would. Never import through the repository folder that holds the code (for "
    "example a src. prefix): that folder is not on the import path. Output: print the last line with "
    "print(json.dumps({\"observations\": obs})). Never print the dict itself, its repr or str: only JSON is read.")
SRC_DIR = "src"


def python_rule(version: str) -> str:
    """Prompt rule naming the Python that runs the probes."""
    return (f"\n\nPython version: the probes run on Python {version}. Use only syntax and standard library "
            f"features that exist in Python {version}.")


# One rewrite of a probe that crashed on every main-side run. It sees only the probe's own code and its main-side
# error output, never anything from the PR side. The verdict cap is enforced in code (ops/daily_run.cap_rewrite).
REWRITE_PROMPT = """A probe you wrote crashed on the BASE side of a pull request on every run, so it observed
nothing. You get its code and the error output from the base side. Rewrite it so it runs. Keep what it checks, the
observation names it prints and the JSON last line. Use the package's public API, the way its users and its own
test suite do (for example pytest's pytester fixture for pytest plugins and hooks); do not construct internal or
private objects directly, and do not rely on deprecated constructors. Answer with JSON only: {"probes": [one probe
with the same id, about, claims and the new code]}."""
MAX_ERROR_CHARS = 4000


def rewrite_probe(provider, ctx: dict, code: str, main_error: str, python_version: str | None,
                  product: bool = False) -> tuple[str | None, str | None]:
    """(new code, None) or (None, why not). The new code passes the same checks as a first answer."""
    prompt = REWRITE_PROMPT + (PRODUCT_PROBE_RULES if product else "") + (
        python_rule(python_version) if python_version else "")
    user = f"Probe code:\n{code}\n\nBase-side error output (last part):\n{(main_error or '')[-MAX_ERROR_CHARS:]}"
    try:
        resp = provider.complete_json("probes", prompt, user, PROBES_SCHEMA, ctx)
    except ProviderError as e:
        return None, f"rewrite request failed: {e}"
    got = ((resp or {}).get("probes") or [None])[0]
    if not isinstance(got, dict):
        return None, "the rewrite answer had no probe"
    new = _unescape_code(got.get("code"))
    why = validate_probe({"id": "rewrite", "code": new, "claims": []}, set(), python_version)
    if why:
        return None, f"rewrite rejected: {why}"
    return new, None
UNLINKED_REASON = ("no probe listed the claim ids it checks, so its results could not be tied to any claim; in each "
                   "probe, \"claims\" must name the claim ids it checks and the observation names that cover them")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# Product checks only: a quote may lose its Markdown when the model copies it ("`a=b`" quoted as "a=b"). Only
# PAIRED marks around a span are removed (`code`, **b**, __b__, *i*, _i_ at word boundaries); an underscore inside a
# word is kept, so "abc" never matches "a_b_c". Dashes, arrows and quotes are unified. Study runs keep the exact match.
_PAIRED = [re.compile(r"`([^`\n]+)`"),
           re.compile(r"\*\*(?=\S)([^*\n]+?)(?<=\S)\*\*"),
           re.compile(r"(?<![\w_])__(?=\S)([^_\n]+?)(?<=\S)__(?![\w_])"),
           re.compile(r"(?<![\w*])\*(?=[^\s*])([^*\n]+?)(?<=[^\s*])\*(?![\w*])"),
           re.compile(r"(?<![\w_])_(?=[^\s_])([^_\n]+?)(?<=[^\s_])_(?![\w_])")]
_LOOSE_MAP = str.maketrans({"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
                            "\u2015": "-", "\u2212": "-", "\u2018": "'", "\u2019": "'", "\u201a": "'",
                            "\u201b": "'", "\u2032": "'", "\u201c": '"', "\u201d": '"', "\u201e": '"',
                            "\u201f": '"', "\u2033": '"', "\u2192": "->", "\u27f6": "->", "\u21d2": "=>",
                            "\u27f9": "=>"})
LOOSE_MIN_CHARS = 20      # a shorter quote must match exactly
LOOSE_MIN_KEPT = 0.8      # a quote that loses more than a fifth of its characters to normalising is not matched


def loose_norm(s: str) -> str:
    """Whitespace collapsed, paired Markdown marks removed, dashes, arrows and quotes unified."""
    t = _norm((s or "").translate(_LOOSE_MAP))
    for rx in _PAIRED:
        t = rx.sub(r"\1", t)
    return _norm(t)


def loose_quote_ok(quote: str) -> str | None:
    """The normalised quote if it may be matched loosely, else None (too short, or mostly lost to normalising)."""
    raw = _norm(quote)
    lq = loose_norm(quote)
    if len(lq) < LOOSE_MIN_CHARS or not raw or len(lq) < LOOSE_MIN_KEPT * len(raw):
        return None
    return lq


def grounded_claims(raw: dict, title: str, body: str | None, loose: bool = False) -> tuple[list, list]:
    """(kept, rejected): a claim is kept only if its source_quote is found in the title or description.

    loose (product checks only): a quote that is not found as written is compared again after loose_norm on both
    sides. A claim kept that way carries quote_match "loose", so the record shows every such match."""
    text = _norm(title) + " \n " + _norm(body)
    loose_text = (loose_norm(title) + " \n " + loose_norm(body)) if loose else ""
    kept, rejected = [], []
    for c in (raw or {}).get("claims", [])[:20]:
        q = _norm(c.get("source_quote", ""))
        valid = c.get("expect") in ("same", "differs") and c.get("id")
        ok = bool(q) and q in text and valid
        if not ok and loose and valid:
            lq = loose_quote_ok(c.get("source_quote", ""))
            if lq and lq in loose_text:
                kept.append(c | {"quote_match": "loose"})
                continue
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


def validate_probe(p: dict, claim_ids: set, python_version: str | None = None) -> str | None:
    """None if the model's probe is acceptable, else why not. python_version: the Python that will run the probe;
    the code must also parse with that version's grammar (poc/probe_python.py)."""
    if not ID_RE.match(str(p.get("id", ""))):
        return f"bad probe id {p.get('id')!r}"
    code = p.get("code") or ""
    if len(code) > MAX_CODE_CHARS:
        return f"code too long ({len(code)} chars > {MAX_CODE_CHARS})"
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"code does not parse: {e.msg} (line {e.lineno})"
    if python_version:
        from poc import probe_python
        why = probe_python.grammar_error(code, python_version)
        if why:
            return f"code is {why}"
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


def src_packages(base_root) -> set:
    """Top-level import names under a src layout: the base side has a src/ folder that is not itself a package,
    and each name is a package folder or a module inside it. Empty when the project has no such layout."""
    src = Path(base_root) / SRC_DIR
    if not src.is_dir() or (src / "__init__.py").exists():
        return set()
    out = set()
    for c in src.iterdir():
        if c.is_dir() and c.name.isidentifier() and ((c / "__init__.py").is_file() or any(c.glob("*.py"))):
            out.add(c.name)
        elif c.is_file() and c.suffix == ".py" and c.stem.isidentifier():
            out.add(c.stem)
    return out


def fix_src_imports(code: str, packages: set) -> tuple[str, str | None]:
    """(code, None) with every import of the layout folder rewritten to the installed import name, or
    (code, why) when the probe imports that folder in a way that cannot be rewritten safely.

    `import src.pkg.mod` -> `import pkg.mod` only with an alias (otherwise the name src would still be used);
    `from src.pkg.mod import x` -> `from pkg.mod import x`; `from src import pkg` -> `import pkg`. Anything else
    that names src (bare `import src`, a relative import, a name not under the src folder, any other use of the
    name src) is rejected, so the probe never runs with an import that cannot work."""
    if not packages:
        return code, None
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, None   # validate_probe reports it
    edits = []   # (lineno, end_lineno, replacement source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if not any(a.name == SRC_DIR or a.name.startswith(SRC_DIR + ".") for a in node.names):
                continue
            parts = []
            for a in node.names:
                if a.name == SRC_DIR or a.name.startswith(SRC_DIR + "."):
                    rest = a.name[len(SRC_DIR) + 1:]
                    if not rest or rest.split(".")[0] not in packages or not a.asname:
                        return code, f"imports the {SRC_DIR}/ folder ({a.name}); import the installed package by its import name"
                    parts.append(f"{rest} as {a.asname}")
                else:
                    parts.append(a.name + (f" as {a.asname}" if a.asname else ""))
            edits.append((node, "import " + ", ".join(parts)))
        elif isinstance(node, ast.ImportFrom) and node.module and (
                node.module == SRC_DIR or node.module.startswith(SRC_DIR + ".")):
            if node.level:
                continue   # a relative import is not the layout folder
            rest = node.module[len(SRC_DIR) + 1:]
            names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in node.names)
            if rest:
                if rest.split(".")[0] not in packages:
                    return code, f"imports {node.module}, which is not a package in the {SRC_DIR}/ folder"
                edits.append((node, f"from {rest} import {names}"))
            else:
                if not all(a.name in packages for a in node.names):
                    return code, f"imports from the {SRC_DIR}/ folder a name that is not a package in it"
                edits.append((node, f"import {names}"))
    if not edits:
        return code, None
    lines = code.splitlines(keepends=True)
    for node, new in sorted(edits, key=lambda e: e[0].lineno, reverse=True):
        start, end = node.lineno - 1, node.end_lineno - 1
        indent = lines[start][:node.col_offset]
        # Rewrite only an import that is the whole statement on its own lines, so nothing else can change.
        tail = lines[end][node.end_col_offset:].strip()
        if indent.strip() or (tail and not tail.startswith("#")):
            return code, f"imports the {SRC_DIR}/ folder on a line shared with other code"
        lines[start:end + 1] = [indent + new + "\n"]
    fixed = "".join(lines)
    try:
        ftree = ast.parse(fixed)
    except SyntaxError:
        return code, f"imports the {SRC_DIR}/ folder and could not be rewritten"
    for node in ast.walk(ftree):   # fail closed: nothing may still refer to the layout folder
        if isinstance(node, ast.Name) and node.id == SRC_DIR:
            return code, f"uses the name {SRC_DIR} after its imports were rewritten"
        if isinstance(node, ast.Import) and any(a.name.split(".")[0] == SRC_DIR for a in node.names):
            return code, f"imports the {SRC_DIR}/ folder"
        if isinstance(node, ast.ImportFrom) and not node.level and (node.module or "").split(".")[0] == SRC_DIR:
            return code, f"imports the {SRC_DIR}/ folder"
    return fixed, None


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
             base_root: Path, pr_roots: list, outdir: Path, product: bool = False,
             python_version: str | None = None) -> dict:
    """product: a product check. It adds PRODUCT_PROBE_RULES to the probes prompt and rewrites or rejects imports
    of a src/ layout folder. A study run (product False) is unchanged. python_version: the Python that will run the
    probes; the prompt names it and probes that do not parse with its grammar are rejected."""
    from poc import run_progress

    probes_prompt = PROBES_PROMPT + PRODUCT_PROBE_RULES if product else PROBES_PROMPT
    if python_version:
        probes_prompt += python_rule(python_version)
    layout = src_packages(base_root) if product else set()

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
    kept, rejected = grounded_claims(raw, title, body, loose=product)
    out["claims"], out["rejected_claims"] = kept, rejected
    loose = [{"claim": c.get("id"), "source_quote": c.get("source_quote")} for c in kept if c.get("quote_match") == "loose"]
    if loose:
        out["loose_quote_matches"] = loose
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
    if product and testable:   # product checks only: broad "nothing else changes" claims need varied inputs
        from poc import broad_claims
        probes_prompt = probes_prompt + broad_claims.probe_rule(testable)
    run_progress.emit("probes", "super", "Super is writing behaviour probes")
    try:
        resp = provider.complete_json("probes", probes_prompt, user, PROBES_SCHEMA, ctx)
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
            resp = provider.complete_json("probes", probes_prompt, retry_user, PROBES_SCHEMA, ctx)
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
            again = provider.complete_json("probes", probes_prompt, retry_user, PROBES_SCHEMA, ctx)
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
        why = validate_probe(p, set(by_id), python_version)
        if not why and layout:
            before = p["code"]
            p["code"], why = fix_src_imports(before, layout)
            if not why and p["code"] != before:
                out.setdefault("rewritten_imports", []).append(p["id"])
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
        out["probes"].append({"path": path, "freeze": freeze.freeze(path, gen, inputs)})
    return out
