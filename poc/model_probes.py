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
import fnmatch
import io
import json
import re
import tokenize
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
    "print(json.dumps({\"observations\": obs})). Never print the dict itself, its repr or str: only JSON is read."
    " Return values: observe what the changed call returns, not the object you passed in. Many calls return a new"
    " object and leave their argument unchanged;"
    " read the result from the return value, not from the input. A probe whose values are all empty on both sides"
    " proves nothing and the check cannot be verified. Claims: every probe must list in \"claims\" the claim"
    " ids it checks, and its observation names must start with those ids.")
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


COVER_REASON = ("some \"covers\" name no observation the probe code records ({}); each cover must be an observation "
                "name the code prints, or an fnmatch pattern that matches some of them")


def recorded_names(code: str) -> tuple[set, set] | None:
    """(names, prefixes) of observation names a probe's code can record: string keys of dict literals and of
    subscript stores (obs["c1.x"] = ...), and the constant start of f-string keys (obs[f"c1.{w}"] -> "c1.").
    None when the code also stores under a key that is neither, or does not parse: then nothing can be told."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return None
    names, prefixes = set(), set()

    def key(k) -> bool:
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            names.add(k.value)
            return True
        if isinstance(k, ast.JoinedStr):
            head = ""
            for part in k.values:
                if not (isinstance(part, ast.Constant) and isinstance(part.value, str)):
                    break
                head += part.value
            prefixes.add(head)
            return True
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k in node.keys:
                if k is not None:
                    key(k)
        elif (isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store) and not _is_sys_modules(node.value)
              and not key(node.slice)):
            return None
    return names, prefixes


def _is_sys_modules(node) -> bool:
    """sys.modules[...] = ... installs a module; it is not an observation key."""
    return (isinstance(node, ast.Attribute) and node.attr == "modules" and isinstance(node.value, ast.Name)
            and node.value.id == "sys")


def _pattern_can_match(pat: str, names: set, prefixes: set) -> bool:
    if any(fnmatch.fnmatchcase(n, pat) for n in names):
        return True
    head = re.split(r"[*?\[]", pat, maxsplit=1)[0]
    return any(head.startswith(pre) or pre.startswith(head) for pre in prefixes)


def unmatched_covers(p: dict, id_covers_count: bool = False) -> list[str]:
    """"C1:c1.row0" for each cover of a probe's claims that no observation name its code records can match. Empty
    when the code's names cannot be told (recorded_names returns None): a cover is never judged on a guess."""
    found = recorded_names(_unescape_code(p.get("code")))
    if found is None:
        return []
    names, prefixes = found
    return [f"{c.get('id')}:{pat}" for c in p.get("claims") or [] if isinstance(c, dict)
            for pat in c.get("covers") or [] if isinstance(pat, str)
            and (id_covers_count or not _is_id_cover(pat, c.get("id")))
            and not _pattern_can_match(pat, names, prefixes)]


def _is_id_cover(pat: str, cid) -> bool:
    """A cover that is only the claim's own id ("C1", "c1*", "C1.*"). Judging already links such covers by id
    (poc/claim_hygiene.py), so it is not asked about again."""
    return str(pat).lower().rstrip("*").rstrip(".") == str(cid or "").lower() and bool(cid)


def _names_per_claim(probes: list) -> dict:
    """Claim id -> the observation names (or name prefixes) its covers match, over all probes. A probe whose
    names cannot be told adds nothing, so a retry that hides its names never counts as keeping them."""
    got: dict = {}
    for q in probes:
        found = recorded_names(_unescape_code(q.get("code")))
        for c in q.get("claims") or []:
            if not isinstance(c, dict):
                continue
            hit = got.setdefault(c.get("id"), set())
            if found is None:
                continue
            names, prefixes = found
            for pat in c.get("covers") or []:
                if isinstance(pat, str) and not _is_id_cover(pat, c.get("id")):
                    hit |= {n for n in names if fnmatch.fnmatchcase(n, pat)}
                    head = re.split(r"[*?\[]", pat, maxsplit=1)[0]
                    hit |= {pre + "*" for pre in prefixes if head.startswith(pre) or pre.startswith(head)}
    return got


def retry_weakens(first: list, retry: list, covers_must_drop: bool = True) -> str | None:
    """Why a retry answer is not kept, or None. Kept only when it has (a) at least as many usable probes,
    (b) for each claim at least as many matched observation names, and (c) fewer unmatched covers, where a
    cover that is only the claim id counts as unmatched, so swapping a real name for "C1.*" is no gain.
    covers_must_drop=False skips (c) only; the unlinked retry uses it, as a first answer with no linked claim
    has no covers that could drop."""
    if len(retry) < len(first):
        return "the retry had fewer usable probes"
    n1, n2 = _names_per_claim(first), _names_per_claim(retry)
    lost = sorted(str(k) for k, v in n1.items() if len(n2.get(k, ())) < len(v))
    if lost:
        return "the retry matched fewer observation names for " + ", ".join(lost)
    strict = lambda ps: sum(len(unmatched_covers(q, id_covers_count=True)) for q in ps)  # noqa: E731
    if covers_must_drop and strict(retry) >= strict(first):
        return "the retry did not leave fewer unmatched covers"
    return None


def _linked_ids(probes: list) -> set:
    return {c.get("id") for q in probes for c in q.get("claims") or [] if isinstance(c, dict)}


def unlinked_retry_rule(claims: list) -> str:
    """The retry text for probes that linked no claim: the testable claims with their ids, and the rule that every
    probe names at least one of those ids."""
    listed = "\n".join(f"- {c.get('id')} (expect {c.get('expect')}): {c.get('text')}" for c in claims)
    return ("The testable claims, with their ids, are:\n" + listed + "\nEvery probe must list at least one of these "
            "claim ids in its \"claims\", with the observation names that cover it. Follow the coverage rule: write at "
            "least one probe per testable claim.")


def unlinked_retry_weakens(first: list, retry: list, claim_ids: set) -> str | None:
    """Why the retry for probes that linked no claim is not kept, or None. Every usable probe must name at least one
    known claim id, and the #177 rules (retry_weakens) still apply."""
    if not retry or not _linked_ids(retry) & claim_ids:
        return "the retry linked no claim either"
    if any(not {c.get("id") for c in q.get("claims") or [] if isinstance(c, dict)} & claim_ids for q in retry):
        return "a retry probe named no claim id"
    return retry_weakens(first, retry, covers_must_drop=False)


PARSE_REPAIR_TRIES = 2   # fixed cap on repair calls for probes whose code does not parse; model calls only


def parse_error(code) -> dict | None:
    """The exact SyntaxError of a probe's code (after unescaping), or None when it parses."""
    code = _unescape_code(code)
    try:
        ast.parse(code if isinstance(code, str) else "")
    except SyntaxError as e:
        text = (e.text or "").rstrip("\n")
        return {"message": e.msg, "line": e.lineno, "offset": e.offset, "code_line": text[:300]}
    return None


_OBS_KEY = re.compile(r"""['"]([A-Za-z_][\w-]*(?:\.[\w-]+)+)['"]""")


def _const_len(node) -> int | None:
    """How many items a for-loop's iterable has, when that can be read: a literal list/tuple/set, range() with
    constant arguments, or enumerate()/list()/tuple()/sorted()/reversed() of one of those."""
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return len(node.elts)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        f, args = node.func.id, node.args
        if f == "range" and args and all(isinstance(x, ast.Constant) and type(x.value) is int for x in args):
            try:
                return len(range(*[x.value for x in args]))
            except ValueError:
                return None
        if f in ("enumerate", "list", "tuple", "sorted", "reversed") and len(args) >= 1:
            return _const_len(args[0])
    return None


_STOPS = (ast.Break, ast.Continue, ast.Return, ast.Raise)


def _live(stmts: list) -> list:
    """The statements of a block that can run: none after an unconditional break/continue/return/raise, and no
    `if False:` / `if 0:` bodies (their else is kept)."""
    out = []
    for st in stmts:
        if isinstance(st, ast.If) and isinstance(st.test, ast.Constant):
            out += _live(st.body if st.test.value else st.orelse)
            continue
        out.append(st)
        if isinstance(st, _STOPS):
            break
    return out


def _ast_counts(code) -> dict | None:
    """Observation keys and inputs of code that parses, read from its AST so keys in comments, docstrings and dead
    code do not count. Keys: dotted names from recorded_names (#177) found in live code; an f-string key inside a loop
    over a readable iterable counts once per item. Inputs: the most items of a readable loop, 1 when its body breaks
    unconditionally. None when the code does not parse or stores under a key that cannot be read."""
    code = _unescape_code(code) if isinstance(code, str) else ""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    if recorded_names(code) is None:
        return None
    names, fkeys, inputs = set(), set(), [0]

    def walk(stmts, mult):
        for st in _live(stmts):
            if isinstance(st, (ast.For, ast.AsyncFor)):
                n = _const_len(st.iter)
                body = _live(st.body)
                if n is not None and any(isinstance(b, ast.Break) for b in body):
                    n = min(n, 1)
                if n is not None:
                    inputs[0] = max(inputs[0], n)
                walk(st.body, mult * n if n else mult)
                walk(st.orelse, mult)
                continue
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                walk(st.body, mult)
                continue
            subs = [getattr(st, f) for f in ("body", "orelse", "finalbody") if isinstance(getattr(st, f, None), list)]
            subs += [h.body for h in getattr(st, "handlers", [])]
            for node in ast.walk(st) if not subs else _shallow(st):
                _keys(node, mult)
            for b in subs:
                walk(b, mult)

    def _keys(node, mult):
        if isinstance(node, ast.comprehension):   # [... for i in range(100)] reads 100 inputs, as the text does
            n = _const_len(node.iter)
            if n is not None:
                inputs[0] = max(inputs[0], n)
        ks = []
        if isinstance(node, ast.Dict):
            ks = [k for k in node.keys if k is not None]
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store) and not _is_sys_modules(node.value):
            ks = [node.slice]
        for k in ks:
            if isinstance(k, ast.Constant) and isinstance(k.value, str) and _OBS_KEY.fullmatch(repr(k.value)):
                names.add(k.value)
            elif isinstance(k, ast.JoinedStr):
                fkeys.add((ast.dump(k), mult))

    walk(tree.body, 1)
    return {"keys": len(names) + sum(m for _, m in fkeys), "inputs": inputs[0]}


def _shallow(st):
    """Nodes of a compound statement outside its nested blocks (its test, iterable, items...)."""
    for f, v in ast.iter_fields(st):
        if f in ("body", "orelse", "finalbody", "handlers"):
            continue
        for x in v if isinstance(v, list) else [v]:
            if isinstance(x, ast.AST):
                yield from ast.walk(x)


def _tolerant_tokens(code) -> list:
    """(type, string) tokens of code that may not parse, without comments, line breaks or indentation. A line that
    breaks tokenizing is skipped and tokenizing goes on from the next one, so line breaks alone change nothing."""
    text = _unescape_code(code) if isinstance(code, str) else ""
    toks, lines = [], text.splitlines(keepends=True)
    start = 0
    while start < len(lines):
        last = start
        try:
            for t in tokenize.generate_tokens(io.StringIO("".join(lines[start:])).readline):
                last = start + t.start[0] - 1
                if t.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
                    continue
                toks.append((t.type, t.string))
            break
        except (tokenize.TokenError, IndentationError, SyntaxError) as e:
            # skip past the line that broke tokenizing and go on from the next one
            line = (e.args[1][0] if isinstance(e, tokenize.TokenError) and len(e.args) > 1
                    and isinstance(e.args[1], tuple) else getattr(e, "lineno", None))
            stop = start + line if isinstance(line, int) and line > 0 else last + 1
            start = max(stop, last + 1, start + 1)
            toks.append((tokenize.OP, ";"))
    return toks


def _token_obs_keys(code) -> int:
    """Distinct dotted string keys of code that may not parse, read from its tokens: a string right after `{` or `,`
    and followed by `:` (a dict key), or between `[` and `] =` (a subscript store). Comments, docstrings and other
    strings (import_module('pkg.mod'), mock.patch('pkg.mod.f')) are not in a key position. Tokenizing stops at the
    first token error and keeps what it read; line breaks alone do not change the count."""
    toks = _tolerant_tokens(code)
    names = set()
    for i, (kind, val) in enumerate(toks):
        if kind != tokenize.STRING or i == 0:
            continue
        prev, nxt = toks[i - 1][1], toks[i + 1][1] if i + 1 < len(toks) else ""
        after = toks[i + 2][1] if i + 2 < len(toks) else ""
        dict_key = prev in ("{", ",") and nxt == ":"
        store = (prev == "[" and nxt == "]" and after == "="
                 and [x[1] for x in toks[max(0, i - 4):i - 1]] != ["sys", ".", "modules"])
        if not (dict_key or store):
            continue
        try:
            v = ast.literal_eval(val)
        except (ValueError, SyntaxError):
            continue
        if isinstance(v, str) and _OBS_KEY.fullmatch(repr(v)):
            names.add(v)
    return len(names)


_WRAPS = ("enumerate", "list", "tuple", "sorted", "reversed")


def _token_inputs(code) -> int:
    """The most items of a loop (statement or comprehension) over a literal list, tuple or set, or over range() with
    constant arguments, optionally wrapped in enumerate()/list()/tuple()/sorted()/reversed(); read from the tokens,
    so loops in comments and strings do not count. Mirrors _const_len on the AST."""
    toks = _tolerant_tokens(code)
    vals = [v for _, v in toks]
    best = 0
    for i, v in enumerate(vals):
        if v != "for" or toks[i][0] != tokenize.NAME:
            continue
        j = next((k for k in range(i + 1, min(i + 30, len(vals))) if vals[k] == "in"), None)
        if j is None:
            continue
        j += 1
        while j + 1 < len(vals) and vals[j] in _WRAPS and vals[j + 1] == "(":
            j += 2
        if j + 1 < len(vals) and vals[j] == "range" and vals[j + 1] == "(":
            args, k = [], j + 2
            while k < len(vals) and vals[k] != ")":
                if vals[k] != ",":
                    args.append(vals[k])
                k += 1
            try:
                best = max(best, len(range(*[int(x) for x in args])))
            except (ValueError, TypeError):
                pass
            continue
        if j < len(vals) and vals[j] in ("[", "(", "{"):
            depth, items, seen = 0, 0, False
            for k in range(j, len(vals)):
                x = vals[k]
                if x in ("[", "(", "{"):
                    depth += 1
                    if depth > 1:
                        seen = True
                elif x in ("]", ")", "}"):
                    depth -= 1
                    if depth == 0:
                        items += 1 if seen else 0
                        break
                elif x == "," and depth == 1:
                    items, seen = items + (1 if seen else 0), False
                elif x == "for" and depth == 1:   # a comprehension, not a literal
                    items = 0
                    break
                else:
                    seen = True
            best = max(best, items)
    return best


def original_counts(code) -> dict:
    """Keys and inputs of the original (broken) probe, both read from its tokens."""
    return {"keys": _token_obs_keys(code), "inputs": _token_inputs(code), "read": "tokens"}


def repair_counts(code) -> dict | None:
    """Keys and inputs of a repair, read from its AST only; None when a key cannot be read (no text fallback)."""
    c = _ast_counts(code)
    return dict(c, read="ast") if c is not None else None


def _repair_loses(old_code, new_code) -> tuple[str | None, dict]:
    """Why a parse repair is rejected, and the before and after counts. The broken original is read from its tokens;
    the repair, which parses, from its AST. A repair whose keys cannot be read is rejected."""
    before, after = original_counts(old_code), repair_counts(new_code)
    counts = {"before": before, "after": after}
    if after is None:
        return "the repair stores under a key that cannot be read", counts
    if after["keys"] < before["keys"]:
        return f"the repair has fewer observation keys ({after['keys']} < {before['keys']})", counts
    if after["inputs"] < before["inputs"]:
        return f"the repair has fewer inputs ({after['inputs']} < {before['inputs']})", counts
    return None, counts


def _repair_parse_errors(provider, probes_prompt: str, user: str, ctx: dict, resp, out: dict):
    """Ask the model to fix probes whose code does not parse, giving it each exact parse error (message, line and
    offending code line) and the full code, up to PARSE_REPAIR_TRIES times. A fixed probe replaces the broken one
    (matched by id only). Only the repaired `code` is taken; the original's claims, covers, expect and about are
    kept. A repair with fewer observation keys or fewer inputs than the original (text counts, so a broken original
    still counts) is rejected. Every attempt is recorded in out["parse_repairs"] with its error, attempt number and
    outcome."""
    attempts = out.setdefault("parse_repairs", [])
    for n in range(1, PARSE_REPAIR_TRIES + 1):
        probes = [p for p in (resp or {}).get("probes", [])[:MAX_PROBES] if isinstance(p, dict)]
        broken = [(i, p, parse_error(p.get("code"))) for i, p in enumerate(probes)]
        broken = [(i, p, e) for i, p, e in broken if e]
        if not broken:
            return resp
        lines = []
        for _, p, e in broken:
            lines.append(f"Probe {p.get('id')!r}: SyntaxError: {e['message']} (line {e['line']}, column {e['offset']})"
                         f"\nOffending line: {e['code_line']}\nFull code as received:\n{_unescape_code(p.get('code'))}")
        ask = (user + "\n\nThese probes from your previous answer do not parse as Python. Return the same probes "
               "with their code fixed (same ids, real line breaks, no escaped newlines):\n\n" + "\n\n".join(lines))
        try:
            again = provider.complete_json("probes", probes_prompt, ask, PROBES_SCHEMA, ctx)
        except ProviderError as ex:
            for _, p, e in broken:
                attempts.append({"attempt": n, "probe": p.get("id"), "error": e, "outcome": f"provider error: {ex}"})
            return resp
        got = [q for q in (again or {}).get("probes", []) if isinstance(q, dict)]
        by_id = {_tidy_id(q.get("id")): q for q in got if isinstance(q.get("id"), str)}
        fixed_list = list(probes)
        for i, p, e in broken:
            q = by_id.get(_tidy_id(p.get("id")) if isinstance(p.get("id"), str) else None)
            counts = None
            if q is None:
                outcome = "no fixed probe returned"
            else:
                still = parse_error(q.get("code"))
                lost, counts = _repair_loses(p.get("code"), q.get("code"))
                if still is not None:
                    outcome = f"still fails: {still['message']} (line {still['line']})"
                elif lost:
                    outcome = "rejected: " + lost
                else:
                    outcome = "fixed"
                    fixed_list[i] = dict(p, code=q.get("code"))
            attempts.append({"attempt": n, "probe": p.get("id"), "error": e, "outcome": outcome,
                             **({"counts": counts} if counts else {})})
        resp = dict(resp or {}, probes=fixed_list)
    return resp


def _usable(resp, claim_ids: set) -> list:
    """The probes of a reply that pass validate_probe (after tidying ids and unescaping code)."""
    return [p for p in (resp or {}).get("probes", [])[:MAX_PROBES] if isinstance(p, dict)
            and not validate_probe(dict(p, id=_tidy_id(p.get("id")), code=_unescape_code(p.get("code"))), claim_ids)]


def generate(provider: Provider, repo: str, pr: int, title: str, body: str | None, base_files: dict,
             base_root: Path, pr_roots: list, outdir: Path, product: bool = False,
             python_version: str | None = None, diff: str | None = None) -> dict:
    """product: a product check. It adds PRODUCT_PROBE_RULES to the probes prompt and rewrites or rejects imports
    of a src/ layout folder. A study run (product False) is unchanged. python_version: the Python that will run the
    probes; the prompt names it and probes that do not parse with its grammar are rejected. diff: the PR diff, read
    only to see whether an existing pattern is edited (poc/boundary_probes.py); only base-side text reaches the prompt."""
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
    if product:   # product checks only: an edited existing pattern needs inputs just past the old match boundary
        from poc import boundary_probes
        rule = boundary_probes.probe_rule(diff, testable)
        if rule:
            probes_prompt = probes_prompt + rule
            out["boundary_rule"] = boundary_probes.modified_patterns(diff)
    run_progress.emit("probes", "super", "Super is writing behaviour probes")
    try:
        resp = provider.complete_json("probes", probes_prompt, user, PROBES_SCHEMA, ctx)
    except ProviderError as e:
        out["errors"].append(str(e))
        return out
    by_id = {c["id"]: c for c in testable}
    resp = _repair_parse_errors(provider, probes_prompt, user, ctx, resp, out)
    if not out["parse_repairs"]:
        out.pop("parse_repairs")
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
        # The retry is sent the claim list with its ids and must name at least one of them in every probe. Links
        # come only from the model's own answer; nothing here links a probe to a claim by name or any other guess.
        out["retried"] = {"why": [UNLINKED_REASON]}
        retry_user = (user + "\n\nYour previous answer had probes, but " + UNLINKED_REASON + ". "
                      + unlinked_retry_rule(testable))
        try:
            again = provider.complete_json("probes", probes_prompt, retry_user, PROBES_SCHEMA, ctx)
        except ProviderError as e:
            out["errors"].append(f"retry: {e}")
        else:
            usable2 = _usable(again, set(by_id))
            weak = unlinked_retry_weakens(usable, usable2, set(by_id))
            if weak is None:
                resp = again
            else:
                out["retried"]["kept_first_answer"] = weak
    elif by_id:
        # Claims are linked, but a cover names no observation the code records. Its claim would then see nothing
        # and the differences under the real names would look unclaimed. Ask once more; keep the retry only when
        # retry_weakens finds nothing (a model call only, no search credits), so no probe, link or name is lost.
        bad = [x for p in usable for x in unmatched_covers(p)]
        if bad:
            why = COVER_REASON.format(", ".join(bad[:6]))
            out["retried"] = {"why": [why]}
            try:
                again = provider.complete_json("probes", probes_prompt, user + "\n\nYour previous answer had probes, but "
                                               + why + ".", PROBES_SCHEMA, ctx)
            except ProviderError as e:
                out["errors"].append(f"retry: {e}")
            else:
                usable2 = _usable(again, set(by_id))
                weak = retry_weakens(usable, usable2)
                if weak is None and not _linked_ids(usable) <= _linked_ids(usable2):
                    weak = "the retry linked fewer claims"
                if weak is None:
                    resp = again
                else:
                    out["retried"]["kept_first_answer"] = weak
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

    left = [x for p in draft_probes for x in unmatched_covers(p)]
    if left:
        out["unmatched_covers"] = left   # shown on the record; judging still decides from the observed names
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
