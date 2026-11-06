"""Names a generated probe uses must exist on the base side before the probe runs.

The check reads the base checkout (or the installed base tree) as files. It does not import the
package and it does not run the probe. Nothing here is specific to one library, and a missing
name is never replaced by a lookalike: the message only says what is absent and which names
that same module or package actually contains.

A name the probe only checks for absence is not required to exist. That is a try/except, or
pytest.raises / contextlib.suppress, of ImportError, ModuleNotFoundError, AttributeError or
NameError, or the string passed to hasattr or to getattr with a default. A bare except, or
except Exception, is not that: the probe is still using the name as if it existed.
"""
from __future__ import annotations

import ast
import builtins
from pathlib import Path

_BUILTINS = set(dir(builtins))
_IMPORT_EXC = {"ImportError", "ModuleNotFoundError"}
_ATTR_EXC = {"AttributeError"}
_NAME_EXC = {"NameError"}
_BROAD = {"Exception", "BaseException"}
_LIST_LIMIT = 12


def problems(code: str, base_root) -> list[str]:
    """Concrete problems, in source order. Empty when every required name exists, or when the
    code does not parse (a parse error is reported by the parse repair, not here).

    base_root: the base checkout or its site-packages. None checks only undefined names in the
    probe itself (a name the probe uses and never binds). Imports of modules that are not in
    that tree (the standard library, or a third-party package) are left alone."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return []
    checker = _Checker(Path(base_root) if base_root else None, skip_undefined=_cannot_tell(tree))
    checker.visit(tree)
    return checker.messages()


def _strip_probe_assign(tree: ast.AST) -> ast.AST:
    """Drop the harness ``PROBE = {...}`` assignment. It is not the probe's test code."""
    body = []
    for stmt in getattr(tree, "body", []):
        if isinstance(stmt, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "PROBE" for t in stmt.targets):
            continue
        body.append(stmt)
    return ast.Module(body=body, type_ignores=[])


def local_failure(code: str) -> str | None:
    """Why this probe file must not be executed, or None.

    An empty file (no test statements once the harness PROBE assignment is ignored) and a probe
    that uses a name it never defines are not run. A missing project import is not decided here:
    that needs the base tree, and it is rejected before the file is written."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return None
    from poc.model_probes import EMPTY_PROBE, has_test_code
    body = _strip_probe_assign(tree)
    if not has_test_code(body):
        return EMPTY_PROBE
    undef = [m for m in problems(ast.unparse(body), None) if m.startswith("undefined name")]
    return "; ".join(undef) if undef else None


def mark_unusable(item: dict, why: str) -> dict:
    """A copy of a probe result that cannot count as coverage.

    Its observations are dropped, so a value that happens to match on both sides is not proof
    and is not a pass. Any line count already recorded is kept as changed_lines_touched and the
    covered count is 0."""
    out = dict(item)
    out["status"] = "not_run"
    out["uninformative_reason"] = why
    out["observations"] = []
    cov = dict(out.get("probe_changed_line_coverage") or {})
    touched = cov.get("changed_lines_covered") or 0
    cov["adequacy"] = "not_adequate"
    cov["note"] = why + "; not counted as coverage"
    cov["changed_lines_covered"] = 0
    if "changed_lines_total" not in cov:
        cov["changed_lines_total"] = 0
    if cov.get("status") not in ("measured", "not measured"):
        cov["status"] = "not measured"
    if "why" not in cov:
        cov["why"] = why
    if touched:
        cov["changed_lines_touched"] = touched
    out["probe_changed_line_coverage"] = cov
    return out


def unusable_item(probe_id: str, source: str, path: str, why: str) -> dict:
    """A probe result for a file that was not executed."""
    return mark_unusable({
        "id": probe_id, "source": source, "path": path, "about": why[:300], "claims": [],
        "runs": {"main": [], "pr": []}, "per_run": [], "outputs": {"main": [], "pr": []},
        "probe_changed_line_coverage": {
            "status": "not measured", "why": why, "changed_lines_total": 0, "changed_lines_covered": 0},
    }, why)


def _cannot_tell(tree: ast.AST) -> bool:
    """True when a name used in the probe might have been created dynamically, so an undefined
    name would be a guess. Imports are still checked."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval"}:
            return True
    return False


def _assigned(node) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        out = set()
        for elt in node.elts:
            out |= _assigned(elt)
        return out
    if isinstance(node, ast.Starred):
        return _assigned(node.value)
    return set()


def _exc_names(node) -> set[str] | None:
    """Exception names, or None when the handler catches everything (bare, Exception, BaseException)
    or the type cannot be read."""
    if node is None:
        return None
    if isinstance(node, ast.Name):
        if node.id in _BROAD:
            return None
        return {node.id}
    if isinstance(node, ast.Attribute):
        return {node.attr} if node.attr not in _BROAD else None
    if isinstance(node, ast.Tuple):
        names = set()
        for elt in node.elts:
            got = _exc_names(elt)
            if got is None:
                return None
            names |= got
        return names
    return None


def _excuse_for(names: set[str] | None) -> set[str]:
    if not names:
        return set()
    out = set()
    if names & _IMPORT_EXC:
        out.add("import")
    if names & _ATTR_EXC:
        out.add("attr")
    if names & _NAME_EXC:
        out.add("name")
    return out


def _handler_excuse(handler: ast.ExceptHandler) -> set[str]:
    return _excuse_for(_exc_names(handler.type))


def _call_name(func) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _with_excuse(expr) -> set[str]:
    """pytest.raises(SomeError) and contextlib.suppress(SomeError), including a tuple of errors."""
    if not isinstance(expr, ast.Call) or not expr.args:
        return set()
    if _call_name(expr.func) not in {"raises", "suppress"}:
        return set()
    return _excuse_for(_exc_names(expr.args[0]))


def _presence_skip(node: ast.Call) -> int | None:
    """Index of the string argument that names something whose absence is the point, or None."""
    name = _call_name(node.func)
    if name == "hasattr" and len(node.args) >= 2 and _string(node.args[1]):
        return 1
    if name == "getattr" and len(node.args) >= 3 and _string(node.args[1]):
        return 1
    return None


def _string(node) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


class _Checker(ast.NodeVisitor):
    def __init__(self, base_root: Path | None, skip_undefined: bool):
        self.root = base_root
        self.skip_undefined = skip_undefined
        self.scopes = [_BUILTINS.copy()]
        self.aliases = [{}]   # local name -> imported module, innermost last
        self.excuse = [set()]
        self._msgs = []
        self._undef = []

    def messages(self) -> list[str]:
        out = []
        for msg in self._msgs:
            if msg not in out:
                out.append(msg)
        if self._undef:
            names = []
            for name in self._undef:
                if name not in names:
                    names.append(name)
            out.append("undefined name: " + ", ".join(names))
        return out

    def _bind(self, name: str) -> None:
        self.scopes[-1].add(name)

    def _defined(self, name: str) -> bool:
        return any(name in scope for scope in self.scopes)

    def _alias(self, name: str) -> str | None:
        for table in reversed(self.aliases):
            if name in table:
                return table[name]
        return None

    def _push(self) -> None:
        self.scopes.append(set())
        self.aliases.append({})
        self.excuse.append(self.excuse[-1])

    def _pop(self) -> None:
        self.scopes.pop()
        self.aliases.pop()
        self.excuse.pop()

    def _add(self, msg: str | None) -> None:
        if msg and msg not in self._msgs:
            self._msgs.append(msg)

    def _bind_target(self, node) -> None:
        for name in _assigned(node):
            self._bind(name)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            if "name" not in self.excuse[-1] and not self.skip_undefined and not self._defined(node.id):
                self._undef.append(node.id)
        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            self._bind(node.id)

    def visit_Assign(self, node):
        self.visit(node.value)
        for target in node.targets:
            self._bind_target(target)

    def visit_AnnAssign(self, node):
        if node.value:
            self.visit(node.value)
        self._bind_target(node.target)

    def visit_AugAssign(self, node):
        self.visit(node.value)
        if isinstance(node.target, ast.Name) and "name" not in self.excuse[-1] and not self._defined(node.target.id):
            self._undef.append(node.target.id)
        self._bind_target(node.target)

    def visit_NamedExpr(self, node):
        self.visit(node.value)
        self._bind_target(node.target)

    def visit_Import(self, node):
        for alias in node.names:
            local = alias.asname or alias.name.split(".")[0]
            self._bind(local)
            # `import a.b.c` binds `a`. Attribute lookup starts at `a`, not at `a.b.c`.
            # `import a.b.c as c` binds the whole module.
            self.aliases[-1][local] = alias.name if alias.asname else alias.name.split(".")[0]
            if "import" not in self.excuse[-1]:
                self._add(_missing_module(self.root, alias.name))

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name != "*":
                self._bind(alias.asname or alias.name)
        if node.level or not node.module:
            return
        if "import" in self.excuse[-1]:
            return
        self._add(_missing_module(self.root, node.module))
        for alias in node.names:
            if alias.name == "*":
                continue
            self._add(_missing_attr(self.root, node.module, alias.name))
            child = locate(self.root, node.module + "." + alias.name)
            if child is not None and child.kind != "missing":
                self.aliases[-1][alias.asname or alias.name] = node.module + "." + alias.name

    def visit_Attribute(self, node):
        if isinstance(node.ctx, ast.Load) and "attr" not in self.excuse[-1]:
            chain = _module_chain(node, self._alias)
            if chain:
                self._require_chain(chain[0], chain[1], allow_missing_module="import" in self.excuse[-1])
        self.generic_visit(node)

    def visit_Call(self, node):
        skip = _presence_skip(node)
        if skip is None:
            self.generic_visit(node)
            return
        self.visit(node.func)
        for i, arg in enumerate(node.args):
            if i != skip:
                self.visit(arg)
        for kw in node.keywords:
            if kw.value:
                self.visit(kw.value)

    def visit_FunctionDef(self, node):
        self._function(node)

    def visit_AsyncFunctionDef(self, node):
        self._function(node)

    def _function(self, node):
        self._bind(node.name)
        for deco in node.decorator_list:
            self.visit(deco)
        args = node.args
        for default in list(args.defaults) + list(args.kw_defaults):
            if default is not None:
                self.visit(default)
        self._push()
        for arg in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
            self._bind(arg.arg)
        if args.vararg:
            self._bind(args.vararg.arg)
        if args.kwarg:
            self._bind(args.kwarg.arg)
        for stmt in node.body:
            self.visit(stmt)
        self._pop()

    def visit_Lambda(self, node):
        args = node.args
        for default in list(args.defaults) + list(args.kw_defaults):
            if default is not None:
                self.visit(default)
        self._push()
        for arg in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
            self._bind(arg.arg)
        if args.vararg:
            self._bind(args.vararg.arg)
        if args.kwarg:
            self._bind(args.kwarg.arg)
        self.visit(node.body)
        self._pop()

    def visit_ClassDef(self, node):
        self._bind(node.name)
        for deco in node.decorator_list:
            self.visit(deco)
        for base in node.bases:
            self.visit(base)
        self._push()
        for stmt in node.body:
            self.visit(stmt)
        self._pop()

    def visit_For(self, node):
        self.visit(node.iter)
        self._bind_target(node.target)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_AsyncFor(self, node):
        self.visit_For(node)

    def visit_With(self, node):
        extra = set()
        for item in node.items:
            extra |= _with_excuse(item.context_expr)
            self.visit(item.context_expr)
            if item.optional_vars:
                self._bind_target(item.optional_vars)
        self.excuse.append(self.excuse[-1] | extra)
        for stmt in node.body:
            self.visit(stmt)
        self.excuse.pop()

    def visit_Try(self, node):
        extra = set()
        for handler in node.handlers:
            extra |= _handler_excuse(handler)
        self.excuse.append(self.excuse[-1] | extra)
        for stmt in node.body:
            self.visit(stmt)
        self.excuse.pop()
        for handler in node.handlers:
            self.visit(handler)
        for stmt in node.orelse:
            self.visit(stmt)
        for stmt in node.finalbody:
            self.visit(stmt)

    def visit_ExceptHandler(self, node):
        if node.type:
            self.visit(node.type)
        if node.name:
            self._bind(node.name)
        for stmt in node.body:
            self.visit(stmt)

    def visit_ListComp(self, node):
        self._comp(node, lambda: self.visit(node.elt))

    def visit_SetComp(self, node):
        self._comp(node, lambda: self.visit(node.elt))

    def visit_GeneratorExp(self, node):
        self._comp(node, lambda: self.visit(node.elt))

    def visit_DictComp(self, node):
        self._comp(node, lambda: (self.visit(node.key), self.visit(node.value)))

    def _comp(self, node, visit_elt) -> None:
        # The first iterable is evaluated outside the comprehension. Later iterables see the
        # names bound by earlier targets (`for x in xs for y in x`).
        for i, gen in enumerate(node.generators):
            if i == 0:
                self.visit(gen.iter)
                self._push()
            else:
                self.visit(gen.iter)
            self._bind_target(gen.target)
            for test in gen.ifs:
                self.visit(test)
        visit_elt()
        self._pop()

    def _require_chain(self, module: str, attrs: list[str], allow_missing_module: bool) -> None:
        cur = module
        for attr in attrs:
            loc = locate(self.root, cur)
            if loc is None:
                return
            if loc.kind == "missing":
                if not allow_missing_module:
                    self._add(_missing_module(self.root, cur))
                return
            child = locate(self.root, cur + "." + attr)
            if child is not None and child.kind != "missing":
                cur = cur + "." + attr
                continue
            names = defined_names(loc)
            if names is None or attr in names:
                return
            self._add(_missing_attr(self.root, cur, attr))
            return


def _module_chain(node, alias_of) -> tuple[str, list[str]] | None:
    """(imported module, attribute parts) when `node` is a load rooted at an imported module."""
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name) or not parts:
        return None
    module = alias_of(cur.id)
    if not module:
        return None
    parts.reverse()
    return module, parts


def _missing_module(base_root, dotted: str) -> str | None:
    loc = locate(base_root, dotted)
    if loc is None or loc.kind != "missing":
        return None
    return _describe_missing(base_root, dotted)


def _missing_attr(base_root, module: str, name: str) -> str | None:
    if _missing_module(base_root, module):
        return _missing_module(base_root, module)
    child = locate(base_root, module + "." + name)
    if child is not None and child.kind != "missing":
        return None
    loc = locate(base_root, module)
    if loc is None or loc.kind == "missing":
        return None
    names = defined_names(loc)
    if names is None or name in names:
        return None
    listed = _listing(loc)
    if listed:
        return f"{module}.{name} does not exist; {module} contains: {_format_list(listed)}"
    return f"{module}.{name} does not exist"


def _describe_missing(base_root, dotted: str) -> str:
    parts = dotted.split(".")
    for i in range(len(parts) - 1, 0, -1):
        parent = ".".join(parts[:i])
        loc = locate(base_root, parent)
        if loc is not None and loc.kind != "missing":
            listed = _listing(loc)
            if listed:
                return f"module {dotted} does not exist; {parent} contains: {_format_list(listed)}"
            return f"module {dotted} does not exist"
    return f"module {dotted} does not exist"


def _format_list(names: list[str]) -> str:
    shown = names[:_LIST_LIMIT]
    extra = f" (+{len(names) - _LIST_LIMIT} more)" if len(names) > _LIST_LIMIT else ""
    return ", ".join(shown) + extra


def _listing(loc) -> list[str]:
    names = set()
    if loc.path is not None and loc.kind == "package":
        directory = loc.path if loc.path.is_dir() else loc.path.parent
        names |= _child_modules(directory)
    defined = defined_names(loc)
    if defined:
        names |= {n for n in defined if not n.startswith("_")}
    return sorted(names)


class Located:
    def __init__(self, kind: str, path: Path | None, dotted: str):
        self.kind = kind
        self.path = path
        self.dotted = dotted


def locate(base_root, dotted: str) -> Located | None:
    """Where `dotted` lives under the base tree.

    None when the top-level name is not a module or package in that tree (a standard-library
    or third-party import). kind 'missing' when the top-level name is there but this path is not."""
    if base_root is None:
        return None
    parts = [p for p in str(dotted).split(".") if p]
    if not parts or not all(p.isidentifier() for p in parts):
        return None
    if parts[0] not in _top_levels(base_root):
        return None
    for root in _roots(base_root):
        found = _walk(root, parts, ".".join(parts))
        if found is not None and found.kind != "missing":
            return found
    return Located("missing", None, ".".join(parts))


def defined_names(loc: Located) -> set[str] | None:
    """Module-level names, or None when they cannot be known (binary module, unreadable file,
    or a module that defines __getattr__ or star-imports)."""
    if loc.kind == "extension":
        return None
    if loc.kind == "package" and loc.path is not None and loc.path.is_dir():
        return _child_modules(loc.path)
    if loc.kind in {"module", "package"} and loc.path is not None and loc.path.is_file():
        return _names_in_file(loc.path)
    return None


def _roots(base_root: Path) -> list[Path]:
    base = Path(base_root)
    if not base.is_dir():
        return []
    roots = [base]
    src = base / "src"
    if src.is_dir() and not (src / "__init__.py").exists():
        roots.append(src)
    return roots


def _top_levels(base_root: Path) -> set[str]:
    names = set()
    for root in _roots(base_root):
        try:
            children = list(root.iterdir())
        except OSError:
            continue
        for child in children:
            if _skip(child.name):
                continue
            if child.is_dir() and child.name.isidentifier() and _is_package_dir(child):
                names.add(child.name)
            elif child.is_file():
                stem = _module_stem(child)
                if stem and stem != "__init__":
                    names.add(stem)
    return names


def _skip(name: str) -> bool:
    return (name.startswith(".") or name == "__pycache__" or name.endswith(".egg-info")
            or name.endswith(".dist-info"))


def _is_package_dir(path: Path) -> bool:
    if (path / "__init__.py").is_file():
        return True
    try:
        for child in path.iterdir():
            if child.is_file() and _module_stem(child):
                return True
            if child.is_dir() and not _skip(child.name) and (child / "__init__.py").is_file():
                return True
    except OSError:
        return False
    return False


def _module_stem(path: Path) -> str | None:
    name = path.name
    if name.endswith(".py"):
        return path.stem if path.stem.isidentifier() else None
    if name.endswith(".pyd") or ".so" in name:
        stem = name.split(".", 1)[0]
        return stem if stem.isidentifier() else None
    return None


def _find_ext(directory: Path, part: str) -> Path | None:
    try:
        children = list(directory.iterdir())
    except OSError:
        return None
    for child in children:
        if child.is_file() and _module_stem(child) == part and not child.name.endswith(".py"):
            return child
    return None


def _walk(root: Path, parts: list[str], dotted: str) -> Located | None:
    cur = root
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        py = cur / f"{part}.py"
        ext = _find_ext(cur, part)
        pkg = cur / part
        if py.is_file():
            return Located("module" if last else "missing", py if last else None, dotted)
        if ext is not None:
            return Located("extension" if last else "missing", ext if last else None, dotted)
        if pkg.is_dir() and _is_package_dir(pkg):
            if last:
                init = pkg / "__init__.py"
                return Located("package", init if init.is_file() else pkg, dotted)
            cur = pkg
            continue
        return Located("missing", None, dotted)
    return Located("missing", None, dotted)


def _child_modules(directory: Path) -> set[str]:
    names = set()
    try:
        children = list(directory.iterdir())
    except OSError:
        return names
    for child in children:
        if _skip(child.name):
            continue
        if child.is_file():
            stem = _module_stem(child)
            if stem and stem != "__init__":
                names.add(stem)
        elif child.is_dir() and child.name.isidentifier() and _is_package_dir(child):
            names.add(child.name)
    return names


def _names_in_file(path: Path) -> set[str] | None:
    try:
        tree = ast.parse(path.read_text(errors="replace"))
    except (OSError, SyntaxError):
        return None
    names = set()
    dynamic = False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == "__getattr__":
                dynamic = True
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names |= _assigned(target)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if any(alias.name == "*" for alias in node.names):
                dynamic = True
            else:
                for alias in node.names:
                    names.add(alias.asname or alias.name)
    if path.name == "__init__.py":
        names |= _child_modules(path.parent)
    if dynamic:
        return None
    return names
