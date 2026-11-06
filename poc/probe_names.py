"""Names a generated probe uses must exist on the base side before the probe runs.

The check reads the base checkout (or the installed base tree) as files. It does not import the
package and it does not run the probe. Nothing here is specific to one library, and a missing
name is never replaced by a lookalike: the message only says what is absent and which names
that same module or package actually contains.

A name the probe only checks for absence is not required to exist. That is a try/except, or
pytest.raises / contextlib.suppress, of ImportError, ModuleNotFoundError, AttributeError or
NameError, or the string passed to hasattr or to getattr with a default. A bare except, or
except Exception, is not that: the probe is still using the name as if it existed.

A call the probe makes on a base function or class is also checked against that definition.
An unexpected keyword is not deleted to make the call run: that would keep a different
scenario. A required parameter that is still missing is filled from a base call that passes
that same parameter, and only that parameter, while the probe's other valid arguments stay.
A call we cannot check (*args, **kwargs, or a constructor or method whose parameters are not
in the file) is not run. A different call is not copied in just because it uses the same name.
"""
from __future__ import annotations

import ast
import builtins
import os
from pathlib import Path

_BUILTINS = set(dir(builtins))
_IMPORT_EXC = {"ImportError", "ModuleNotFoundError"}
_ATTR_EXC = {"AttributeError"}
_NAME_EXC = {"NameError"}
_BROAD = {"Exception", "BaseException"}
_LIST_LIMIT = 12


def hides_required_miss(old: str, new: str, base_root) -> str | None:
    """Why a repair is only hiding a name the previous probe used as a real object, or None.

    An initial probe may check that a symbol is absent. A repair may not: if the previous code
    failed because a name does not exist, wrapping that same name in hasattr, getattr with a
    default, or try/except is a fallback, not a test of the change. Both sides then emit the
    same fallback and it is not evidence."""
    before = _analyze(old, base_root)
    after = _analyze(new, base_root)
    if before is None or after is None or not before.required_missing:
        return None
    hidden = [sym for sym in before.required_missing
              if (flags := after.mentions.get(sym)) and all(flags)]
    if not hidden:
        return None
    return ("hides missing name " + ", ".join(hidden)
            + " behind an absence check; that fallback is not evidence")


def _analyze(code: str, base_root):
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return None
    checker = _Checker(Path(base_root) if base_root else None, skip_undefined=_cannot_tell(tree))
    checker.tree = tree
    checker.visit(tree)
    return checker


def problems(code: str, base_root) -> list[str]:
    """Concrete problems, in source order. Empty when every required name exists, or when the
    code does not parse (a parse error is reported by the parse repair, not here).

    base_root: the base checkout or its site-packages. None checks only undefined names in the
    probe itself (a name the probe uses and never binds). Imports of modules that are not in
    that tree (the standard library, or a third-party package) are left alone."""
    checker = _analyze(code, base_root)
    return checker.messages() if checker is not None else []


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
        # ready: names bound so far (module and class bodies run top to bottom).
        # complete: every name bound in a module or function, including ones later in that block.
        # A function body runs only after its module has finished binding, so it sees `complete`.
        # A class body name is not a lexical name inside a method or a comprehension.
        self.ready = [_BUILTINS.copy()]
        self.complete = [_BUILTINS.copy()]
        self.kinds = ["module"]
        self.aliases = [{}]   # local name -> imported module, innermost last
        self.symbols = [{}]   # local name -> ("mod", dotted) or ("attr", module, name)
        self._file_ast = {}
        self.excuse = [set()]
        self._in_body = False
        self._msgs = []
        self._undef = []
        self.required_missing = []
        self.mentions = {}   # qualified name -> whether each use is only an absence check
        self.calls = []      # base calls in this probe: {node, sig, dotted}
        self.unreadable = []  # a base class or method whose parameters cannot be read
        self.tree = None

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
        """A name that has been executed in this block. Also recorded as a completed binding."""
        self.ready[-1].add(name)
        self.complete[-1].add(name)

    def _defined(self, name: str) -> bool:
        seen_function = False
        for i in range(len(self.kinds) - 1, -1, -1):
            if self.kinds[i] == "function":
                seen_function = True
            # Methods and comprehensions do not close over the class body that contains them.
            if self.kinds[i] == "class" and seen_function:
                continue
            pool = self.complete[i] if self._in_body and self.kinds[i] in ("module", "function") else self.ready[i]
            if name in pool:
                return True
        return False

    def _alias(self, name: str) -> str | None:
        for table in reversed(self.aliases):
            if name in table:
                return table[name]
        return None

    def _push(self, kind: str) -> None:
        self.ready.append(set())
        self.complete.append(set())
        self.kinds.append(kind)
        self.aliases.append({})
        self.symbols.append({})
        self.excuse.append(self.excuse[-1])

    def _pop(self) -> None:
        self.ready.pop()
        self.complete.pop()
        self.kinds.pop()
        self.aliases.pop()
        self.symbols.pop()
        self.excuse.pop()

    def _symbol(self, name: str):
        for table in reversed(self.symbols):
            if name in table:
                return table[name]
        return None

    def _mention(self, qualified: str, excused: bool) -> None:
        self.mentions.setdefault(qualified, []).append(excused)

    def _note_missing(self, qualified: str) -> None:
        if qualified not in self.required_missing:
            self.required_missing.append(qualified)

    def visit_Module(self, node):
        self._prebind_block(node.body)
        for stmt in node.body:
            self.visit(stmt)

    def _prebind_block(self, stmts) -> None:
        """Record names a module or function binds, including ones that appear later.

        Function and class bodies are not entered: their assignments are not bindings of this
        block. The function or class name itself is."""
        for stmt in stmts:
            self._prebind_stmt(stmt)

    def _prebind_stmt(self, stmt) -> None:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            self.complete[-1].add(stmt.name)
            return
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                self.complete[-1].update(_assigned(target))
            return
        if isinstance(stmt, ast.AnnAssign):
            self.complete[-1].update(_assigned(stmt.target))
            return
        if isinstance(stmt, ast.AugAssign):
            self.complete[-1].update(_assigned(stmt.target))
            return
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            self._bind_aliases(stmt, into_complete=True)
            return
        if isinstance(stmt, (ast.For, ast.AsyncFor)):
            self.complete[-1].update(_assigned(stmt.target))
            self._prebind_block(stmt.body)
            self._prebind_block(stmt.orelse)
            return
        if isinstance(stmt, ast.While):
            self._prebind_block(stmt.body)
            self._prebind_block(stmt.orelse)
            return
        if isinstance(stmt, (ast.With, ast.AsyncWith)):
            for item in stmt.items:
                if item.optional_vars:
                    self.complete[-1].update(_assigned(item.optional_vars))
            self._prebind_block(stmt.body)
            return
        if isinstance(stmt, ast.If):
            self._prebind_block(stmt.body)
            self._prebind_block(stmt.orelse)
            return
        if isinstance(stmt, ast.Try):
            self._prebind_block(stmt.body)
            for handler in stmt.handlers:
                if handler.name:
                    self.complete[-1].add(handler.name)
                self._prebind_block(handler.body)
            self._prebind_block(stmt.orelse)
            self._prebind_block(stmt.finalbody)
            return

    def _bind_aliases(self, node, into_complete: bool) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                self._remember(local, into_complete)
                dotted = alias.name if alias.asname else alias.name.split(".")[0]
                self.aliases[-1][local] = dotted
                self.symbols[-1][local] = ("mod", dotted)
            return
        for alias in node.names:
            if alias.name == "*":
                continue
            local = alias.asname or alias.name
            self._remember(local, into_complete)
            if node.module and not node.level:
                child = locate(self.root, node.module + "." + alias.name)
                if child is not None and child.kind != "missing":
                    self.aliases[-1][local] = node.module + "." + alias.name
                    self.symbols[-1][local] = ("mod", node.module + "." + alias.name)
                else:
                    self.symbols[-1][local] = ("attr", node.module, alias.name)

    def _remember(self, name: str, into_complete: bool) -> None:
        if into_complete:
            self.complete[-1].add(name)
        else:
            self._bind(name)

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
        self._bind_aliases(node, into_complete=False)
        excused = "import" in self.excuse[-1]
        for alias in node.names:
            self._mention(alias.name, excused)
            if excused:
                continue
            if _missing_module(self.root, alias.name):
                self._add(_missing_module(self.root, alias.name))
                self._note_missing(alias.name)

    def visit_ImportFrom(self, node):
        self._bind_aliases(node, into_complete=False)
        if node.level or not node.module:
            return
        excused = "import" in self.excuse[-1]
        self._mention(node.module, excused)
        if not excused and _missing_module(self.root, node.module):
            self._add(_missing_module(self.root, node.module))
            self._note_missing(node.module)
        for alias in node.names:
            if alias.name == "*":
                continue
            qualified = node.module + "." + alias.name
            self._mention(qualified, excused)
            if excused:
                continue
            if _missing_attr(self.root, node.module, alias.name):
                self._add(_missing_attr(self.root, node.module, alias.name))
                self._note_missing(qualified)

    def visit_Attribute(self, node):
        if isinstance(node.ctx, ast.Load):
            chain = _module_chain(node, self._alias)
            if chain:
                # Record the use even inside an absence check, so a repair cannot hide the name.
                self._require_chain(chain[0], chain[1], allow_missing_module="import" in self.excuse[-1])
        self.generic_visit(node)

    def visit_Call(self, node):
        self._check_call(node)
        skip = _presence_skip(node)
        if skip is None:
            self.generic_visit(node)
            return
        module = _expr_module(node.args[0], self._alias)
        if module and _string(node.args[skip]):
            self._mention(module + "." + node.args[skip].value, True)
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
        self._push("function")
        for arg in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
            self._bind(arg.arg)
        if args.vararg:
            self._bind(args.vararg.arg)
        if args.kwarg:
            self._bind(args.kwarg.arg)
        # Later defs in this function are visible to earlier nested functions.
        self._prebind_block(node.body)
        was = self._in_body
        self._in_body = True
        for stmt in node.body:
            self.visit(stmt)
        self._in_body = was
        self._pop()

    def visit_Lambda(self, node):
        args = node.args
        for default in list(args.defaults) + list(args.kw_defaults):
            if default is not None:
                self.visit(default)
        self._push("function")
        for arg in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
            self._bind(arg.arg)
        if args.vararg:
            self._bind(args.vararg.arg)
        if args.kwarg:
            self._bind(args.kwarg.arg)
        was = self._in_body
        self._in_body = True
        self.visit(node.body)
        self._in_body = was
        self._pop()

    def visit_ClassDef(self, node):
        self._bind(node.name)
        for deco in node.decorator_list:
            self.visit(deco)
        for base in node.bases:
            self.visit(base)
        self._push("class")
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
        was = self._in_body
        for i, gen in enumerate(node.generators):
            if i == 0:
                self.visit(gen.iter)
                # A comprehension is a nested function. Inside a class it must not see the class
                # body names; inside a function it runs when that function runs.
                self._push("function")
                if self._enclosing_is_function():
                    self._in_body = True
            else:
                self.visit(gen.iter)
            self._bind_target(gen.target)
            for test in gen.ifs:
                self.visit(test)
        visit_elt()
        if self._enclosing_is_function():
            self._in_body = was
        self._pop()

    def _enclosing_is_function(self) -> bool:
        # The comprehension's own frame is the last one. Look outside it.
        return any(kind == "function" for kind in self.kinds[:-1])

    def _require_chain(self, module: str, attrs: list[str], allow_missing_module: bool) -> None:
        cur = module
        excused = "attr" in self.excuse[-1] or "import" in self.excuse[-1]
        for attr in attrs:
            qualified = cur + "." + attr
            self._mention(qualified, excused)
            loc = locate(self.root, cur)
            if loc is None:
                return
            if loc.kind == "missing":
                if not allow_missing_module:
                    self._add(_missing_module(self.root, cur))
                    self._note_missing(cur)
                return
            child = locate(self.root, qualified)
            if child is not None and child.kind != "missing":
                cur = qualified
                continue
            names = defined_names(loc)
            if names is None or attr in names:
                return
            if not excused:
                self._add(_missing_attr(self.root, cur, attr))
                self._note_missing(qualified)
            return

    def _check_call(self, node: ast.Call) -> None:
        """Record a base call and report a keyword or argument list that cannot run.

        Skipped when the callable is not a function or class defined in the base tree, when a
        decorator other than staticmethod/classmethod wraps it, or when the signature accepts
        **kwargs. Third-party and builtin calls are not checked. An import that only re-exports
        the name is followed to the definition, so the parameters are the ones that actually run."""
        sig, dotted = self._resolve_callable(node.func)
        if dotted and sig is None:
            if dotted not in self.unreadable:
                self.unreadable.append(dotted)
        elif sig is not None and dotted:
            self.calls.append({"node": node, "sig": sig, "dotted": dotted})
        problem = _call_problem(node, sig)
        if problem:
            self._add(problem)

    def _resolve_callable(self, func):
        """(signature, defining dotted name) of a base call, or (None, None)."""
        if isinstance(func, ast.Name):
            info = self._symbol(func.id)
            if not info or info[0] != "attr":
                return None, None
            return _resolve_named(self, info[1], [info[2]])
        chain = _module_chain(func, self._alias)
        if not chain:
            return None, None
        return _resolve_named(self, chain[0], chain[1])

    def _call_signature(self, func):
        sig, _dotted = self._resolve_callable(func)
        return sig

    def _module_tree(self, module: str):
        loc = locate(self.root, module)
        if loc is None or loc.kind == "missing" or loc.path is None or not loc.path.is_file():
            return None
        key = str(loc.path)
        if key not in self._file_ast:
            try:
                self._file_ast[key] = ast.parse(loc.path.read_text(errors="replace"))
            except (OSError, SyntaxError):
                self._file_ast[key] = None
        return self._file_ast[key]


class _Sig:
    def __init__(self, display: str, names: list[str], posonly: set[str], var_keyword: bool, *,
                 required=None, n_positional=None, vararg: bool = False, kwonly=None, explicit: bool = True):
        self.display = display
        self.names = names
        self.posonly = posonly
        self.var_keyword = var_keyword
        self.kwonly = set(kwonly or ())
        self.required = list(required or ())
        self.vararg = vararg
        self.explicit = explicit
        self.n_positional = (len([n for n in names if n not in self.kwonly])
                             if n_positional is None else n_positional)


def _retarget(sig: _Sig, display: str) -> _Sig:
    """The same parameters, shown under the class that inherits them."""
    return _Sig(display, list(sig.names), set(sig.posonly), sig.var_keyword, required=list(sig.required),
                n_positional=sig.n_positional, vararg=sig.vararg, kwonly=set(sig.kwonly), explicit=sig.explicit)


def _resolve_named(checker, module: str, attrs: list[str]):
    """(signature, defining dotted name) for module.attr.Callable, or (None, None)."""
    if not attrs:
        return None, None
    cur = module
    i = 0
    while i < len(attrs) - 1:
        nxt = cur + "." + attrs[i]
        loc = locate(checker.root, nxt)
        if loc is not None and loc.kind != "missing":
            cur, i = nxt, i + 1
            continue
        break
    name, rest = attrs[i], attrs[i + 1:]
    found = _lookup_def(checker, cur, name)
    if found is None:
        return None, None
    tree, mod, node = found
    dotted = f"{mod}.{node.name}"
    if not rest:
        if isinstance(node, ast.ClassDef):
            return _init_signature(tree, node), dotted
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return _function_signature(node, drop_first=False, display=node.name), dotted
        return None, None
    if len(rest) == 1 and isinstance(node, ast.ClassDef):
        # None signature: the method is not defined on this class, so a parent we cannot see may own it.
        return _method_on(node, rest[0]), dotted + "." + rest[0]
    return None, None


def _lookup_def(checker, module: str, name: str, depth: int = 0):
    """(tree, module, node) of a class or function, following a re-export a few steps.

    ``from .other import Name`` is not a definition. The parameters live on the class or function
    that other module defines. A cycle stops."""
    if depth > 3 or not module or not name:
        return None
    tree = checker._module_tree(module)
    if tree is None:
        return None
    node = next((n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                 and n.name == name), None)
    if node is not None:
        return tree, module, node
    loc = locate(checker.root, module)
    is_package = loc is not None and loc.kind == "package"
    imported = _import_of(tree, name)
    if imported is not None:
        level, source, original = imported
        target = _absolute_module(module, is_package, level, source)
        if target:
            return _lookup_def(checker, target, original, depth + 1)
    # ``from .other import *`` does not name the class. One more step finds it when that
    # module actually defines this name. A cycle stops at the depth limit.
    for level, source in _star_imports(tree):
        target = _absolute_module(module, is_package, level, source)
        if not target or target == module:
            continue
        found = _lookup_def(checker, target, name, depth + 1)
        if found is not None:
            return found
    return None


def _star_imports(tree: ast.AST) -> list[tuple[int, str | None]]:
    found = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
            found.append((node.level or 0, node.module))
    return found


def _import_of(tree: ast.AST, name: str):
    """(level, module, original name) when ``name`` is imported by this module, else None."""
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        for alias in node.names:
            if alias.name == "*":
                continue
            if (alias.asname or alias.name) == name:
                return node.level or 0, node.module, alias.name
    return None


def _absolute_module(current: str, is_package: bool, level: int, source: str | None) -> str | None:
    """The absolute module an import refers to. level 0 is an absolute import."""
    if not level:
        return source
    parts = current.split(".") if current else []
    if not is_package and parts:
        parts = parts[:-1]
    up = level - 1
    if up > len(parts):
        return None
    parts = parts[:len(parts) - up] if up else parts
    if source:
        parts.extend(source.split("."))
    return ".".join(parts) if parts else None


def _method_on(cls: ast.ClassDef, method: str):
    fn = next((n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method),
              None)
    if fn is None:
        return None
    drop = True
    for deco in fn.decorator_list:
        if _decorator_name(deco) == "staticmethod":
            drop = False
    return _function_signature(fn, drop_first=drop, display=f"{cls.name}.{method}")


def _init_signature(tree: ast.AST, cls: ast.ClassDef, depth: int = 0):
    if depth > 3:
        return None
    init = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"), None)
    if init is not None:
        return _function_signature(init, drop_first=True, display=cls.name)
    if not cls.bases:
        # No constructor in this class. A decorator may still add one, so argument counts are not checked.
        return _Sig(cls.name, [], set(), False, explicit=False)
    for base in cls.bases:
        if isinstance(base, ast.Name) and base.id == "object":
            continue
        if not isinstance(base, ast.Name):
            return None
        parent = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == base.id), None)
        if parent is None:
            return None
        sig = _init_signature(tree, parent, depth + 1)
        if sig is None:
            return None
        return _retarget(sig, cls.name)
    return _Sig(cls.name, [], set(), False, explicit=False)


def _decorator_name(node) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _function_signature(node, drop_first: bool, display: str):
    """None when a decorator may have changed the callable. **kwargs means any keyword is allowed."""
    for deco in node.decorator_list:
        if _decorator_name(deco) not in {"staticmethod", "classmethod"}:
            return None
    if any(_decorator_name(deco) == "classmethod" for deco in node.decorator_list):
        drop_first = True
    if any(_decorator_name(deco) == "staticmethod" for deco in node.decorator_list):
        drop_first = False
    args = node.args
    if args.kwarg is not None:
        return _Sig(display, [], set(), True)
    pos = list(args.posonlyargs) + list(args.args)
    kwonly = list(args.kwonlyargs)
    n_default = len(args.defaults)
    required_pos = pos[:len(pos) - n_default] if n_default else list(pos)
    required_kw = [arg for arg, default in zip(kwonly, args.kw_defaults) if default is None]
    posonly = {arg.arg for arg in args.posonlyargs}
    if drop_first and pos:
        dropped = pos[0].arg
        posonly.discard(dropped)
        pos = pos[1:]
        required_pos = [arg for arg in required_pos if arg.arg != dropped]
    names = [arg.arg for arg in pos + kwonly]
    required = [arg.arg for arg in required_pos + required_kw]
    return _Sig(display, names, posonly, False, required=required, n_positional=len(pos),
                vararg=args.vararg is not None, kwonly={arg.arg for arg in kwonly}, explicit=True)


def _param_list(sig: _Sig) -> str:
    shown = ", ".join(sig.names[:_LIST_LIMIT]) or "(none)"
    extra = f" (+{len(sig.names) - _LIST_LIMIT} more)" if len(sig.names) > _LIST_LIMIT else ""
    return shown + extra


def _unchecked(node: ast.Call, sig: _Sig | None) -> str | None:
    """Why this base call cannot be validated, or None when its arguments are visible.

    Not being able to check is not the same as the call being sound. A call we cannot read must
    not run. A third-party call (no base signature) is not this case."""
    if sig is None:
        return None
    if sig.var_keyword:
        return f"{sig.display}() accepts **kwargs, so its keywords cannot be checked"
    if any(kw.arg is None for kw in node.keywords):
        return f"{sig.display}() was called with **mapping, so its keywords cannot be checked"
    if any(isinstance(arg, ast.Starred) for arg in node.args):
        return f"{sig.display}() was called with *args, so its positional arguments cannot be checked"
    return None


def _call_problem(node: ast.Call, sig: _Sig | None) -> str | None:
    """Why this call cannot match the base signature, or None when it can.

    A signature that accepts **kwargs, or a call that passes **mapping, is not judged: the names
    are not visible. Counts are judged only for a definition that is actually written (a function,
    or a class with its own __init__). A class whose constructor is added by a decorator is not
    counted, so a normal construction is not rejected from an empty parameter list."""
    if sig is None or sig.var_keyword or any(kw.arg is None for kw in node.keywords):
        return None
    bad = [kw.arg for kw in node.keywords if kw.arg not in sig.names or kw.arg in sig.posonly]
    if bad:
        quoted = ", ".join(repr(name) for name in bad)
        return f"{sig.display}() got unexpected keyword(s) {quoted}; parameters: {_param_list(sig)}"
    if not sig.explicit or any(isinstance(arg, ast.Starred) for arg in node.args):
        return None
    positional = list(node.args)
    if not sig.vararg and len(positional) > sig.n_positional:
        return (f"{sig.display}() takes {sig.n_positional} positional argument(s) but {len(positional)} "
                f"were given; parameters: {_param_list(sig)}")
    pos_names = [name for name in sig.names if name not in sig.kwonly]
    filled = set(pos_names[:len(positional)])
    for kw in node.keywords:
        if kw.arg in sig.names and kw.arg not in sig.posonly:
            filled.add(kw.arg)
    missing = [name for name in sig.required if name not in filled]
    if sig.vararg:
        missing = [name for name in missing if name in sig.kwonly]
    if missing:
        quoted = ", ".join(repr(name) for name in missing)
        return f"{sig.display}() missing required argument(s) {quoted}; parameters: {_param_list(sig)}"
    return None


def _expr_module(node, alias_of) -> str | None:
    """The imported module a name or attribute chain refers to, if it is one."""
    if isinstance(node, ast.Name):
        return alias_of(node.id)
    chain = _module_chain(node, alias_of)
    if not chain:
        return None
    module, attrs = chain
    return module + "." + ".".join(attrs)


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
    """A directory we can check as a package: it has ``__init__.py``, or it holds a subpackage that does.

    A folder that only contains a loose module (no ``__init__.py``) is not treated as the whole library.
    An import of some other name under that folder is then left alone, the same as a third-party import.
    A package that does have ``__init__.py`` is checked: a submodule the probe names and the folder does not
    contain is missing."""
    if (path / "__init__.py").is_file():
        return True
    try:
        for child in path.iterdir():
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


# How many base files are read while looking for real calls. The walk stops there. It does not
# import the package and it does not use the network.
_SITE_FILES = 250
_SITE_BYTES = 200_000
_SITES_EACH = 8
_USAGE_CHARS = 2000
_SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "node_modules", "dist", "build", ".tox", ".eggs",
    ".mypy_cache", ".ruff_cache", "site-packages",
}


class _Site:
    def __init__(self, dotted: str, rel: str, lineno: int, call: ast.Call, scope: dict, text: str):
        self.dotted = dotted
        self.rel = rel
        self.lineno = lineno
        self.call = call
        self.scope = scope
        self.text = text


def usage_notes(code: str, base_root) -> str:
    """Text for the one existing model retry: the base signature and real calls of names this probe calls.

    Empty when the probe calls nothing we can resolve, or the base tree is not there. This does not
    call the model and it does not read the pull-request tree."""
    checker = _analyze(code, base_root)
    if checker is None or not checker.calls or base_root is None:
        return ""
    order = []
    for item in checker.calls:
        if item["dotted"] not in order:
            order.append(item["dotted"])
    sites = _collect_sites(base_root, set(order[:6]))
    lines = []
    for dotted in order[:6]:
        sig = next(item["sig"] for item in checker.calls if item["dotted"] == dotted)
        required = ", ".join(sig.required) or "(none)"
        bits = [f"{dotted}({_param_list(sig)}); required: {required}"]
        for site in sites.get(dotted, [])[:4]:
            bits.append(f"called in {site.rel}:{site.lineno} as {site.text}")
        lines.append(" | ".join(bits))
    if not lines:
        return ""
    text = "\n".join(lines)
    if len(text) > _USAGE_CHARS:
        text = text[:_USAGE_CHARS] + "\n..."
    return ("\n\nHow the BASE side calls these names, from its own files. Use those parameters and, when "
            "you need a value, the arguments from one of those calls. A parameter that is not in the list "
            "does not exist. Do not invent a value from the pull-request text when a call below already "
            "shows one.\n" + text)


def prepare_calls(code: str, base_root):
    """Bind every unsound base call, or say why the probe must not run.

    Returns (code, notes, reject). notes lists bindings that were applied. reject is a reason when
    a call does not match the base signature and no base call site (and no default) can fill its
    required parameters. The probe's callee is kept: only the arguments change. A call that already
    matches the signature is left as written. Nothing here reads the pull-request tree or the network."""
    checker = _analyze(code, base_root)
    if checker is None or base_root is None:
        return code or "", [], None
    if checker.unreadable:
        name = checker.unreadable[0]
        return (code or "", [],
                f"cannot check {name}: its parameters are not in this file (an inherited constructor or "
                "method we cannot read); the probe is not run")
    if not checker.calls:
        return code or "", [], None
    for item in checker.calls:
        hidden = _unchecked(item["node"], item["sig"])
        if hidden:
            return (code or "", [],
                    f"cannot bind {item['dotted']}: {hidden}; the probe is not run")
    unsound = [item for item in checker.calls if _call_problem(item["node"], item["sig"])]
    if not unsound:
        return code or "", [], None
    sites = _collect_sites(base_root, {item["dotted"] for item in unsound})
    spelling = _spell_map(checker)
    by_id = {id(item["node"]): item for item in checker.calls}
    notes = []
    failed = []

    class _Bind(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            info = by_id.get(id(node))
            if info is None or _call_problem(node, info["sig"]) is None:
                return node
            built = _bind_call(node, info, sites.get(info["dotted"], []), spelling)
            if built is None:
                failed.append(info)
                return node
            notes.append(built[1])
            return built[0]

    new_tree = _Bind().visit(checker.tree)
    if failed:
        info = failed[0]
        problem = _call_problem(info["node"], info["sig"]) or "the call does not match the base signature"
        where = _site_hint(sites.get(info["dotted"], []))
        return (code or "", [],
                f"cannot bind {info['dotted']}: {problem}; an unknown keyword was not removed, because "
                "dropping it would discard the scenario, and it was not mapped to a base parameter."
                f"{where} The probe is not run")
    if not notes:
        return code or "", [], None
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree) + "\n", notes, None


def _spell_map(checker) -> dict:
    """Dotted name or module -> ('name', local) or ('mod', local), from the probe's own imports."""
    out = {}
    table = checker.symbols[0] if checker.symbols else {}
    for local, info in table.items():
        if not info:
            continue
        if info[0] == "mod":
            out.setdefault(info[1], ("mod", local))
        elif info[0] == "attr":
            found = _lookup_def(checker, info[1], info[2])
            dotted = f"{found[1]}.{found[2].name}" if found else f"{info[1]}.{info[2]}"
            out.setdefault(dotted, ("name", local))
    return out


def _spell(dotted: str, spelling: dict):
    """An expression the probe can already write for this base name, or None."""
    kind = spelling.get(dotted)
    if kind and kind[0] == "name":
        return ast.Name(id=kind[1], ctx=ast.Load())
    parts = dotted.split(".")
    for i in range(len(parts) - 1, 0, -1):
        prefix = ".".join(parts[:i])
        kind = spelling.get(prefix)
        if kind and kind[0] == "mod":
            expr = ast.Name(id=kind[1], ctx=ast.Load())
            for attr in parts[i:]:
                expr = ast.Attribute(value=expr, attr=attr, ctx=ast.Load())
            return expr
    return None


def _site_hint(sites: list) -> str:
    """Where a real call of this name sits, so an abstain can name it without copying it."""
    if not sites:
        return " No base call of this name could be read."
    shown = []
    for site in sites[:2]:
        shown.append(f"{site.rel}:{site.lineno} {site.text}")
    return " A base call exists (" + "; ".join(shown) + ") and was not copied in its place."


def _bind_call(node: ast.Call, info: dict, sites: list, spelling: dict):
    """Keep this call's valid arguments. Fill only a missing required parameter from a base call.

    A keyword or positional the signature accepts stays, including the value the probe wrote. An
    unexpected keyword is not deleted: removing it would keep a different call, so this returns None
    and the probe is not run. A required parameter that is still missing, and only that parameter,
    is taken from a base call that passes it. None means the probe must not run."""
    sig = info["sig"]
    if _unchecked(node, sig):
        return None
    pos_names = [name for name in sig.names if name not in sig.kwonly]
    kept_pos = list(node.args[:sig.n_positional])
    kept_kw = []
    dropped = []
    filled_names = set(pos_names[:len(kept_pos)])
    for kw in node.keywords:
        if kw.arg in sig.names and kw.arg not in sig.posonly and kw.arg not in filled_names:
            kept_kw.append(ast.keyword(arg=kw.arg, value=kw.value))
            filled_names.add(kw.arg)
        else:
            dropped.append(kw.arg)
    if dropped:
        # The unknown keyword is part of what the probe was trying to do. Deleting it leaves a
        # call that merely executes, which is not that scenario.
        return None
    missing = [name for name in sig.required if name not in filled_names]
    filled = []
    for name in missing:
        found = _piece(name, pos_names, sites, spelling)
        if found is None:
            return None
        expr, origin = found
        if name in sig.posonly:
            if pos_names.index(name) != len(kept_pos):
                return None
            kept_pos.append(expr)
        else:
            kept_kw.append(ast.keyword(arg=name, value=expr))
        filled.append({"parameter": name, "from": origin})
    if not kept_pos and not kept_kw:
        return None
    call = ast.Call(func=node.func, args=kept_pos, keywords=kept_kw)
    if _call_problem(call, sig):
        return None
    return call, {"target": info["dotted"], "how": "filled" if filled else "kept",
                  "dropped": dropped, "filled": filled, "call": ast.unparse(call)}


def _render_site(site: _Site, spelling: dict):
    """The site's argument list, with names inlined, or None when a value cannot be copied."""
    def resolve(func):
        return _resolve_copied(func, site)

    args = []
    for arg in site.call.args:
        if isinstance(arg, ast.Starred):
            return None
        got = _reduce(arg, site.scope, resolve, spelling, 0)
        if got is None:
            return None
        args.append(got)
    keywords = []
    for kw in site.call.keywords:
        if kw.arg is None:
            return None
        got = _reduce(kw.value, site.scope, resolve, spelling, 0)
        if got is None:
            return None
        keywords.append(ast.keyword(arg=kw.arg, value=got))
    return ast.Call(func=ast.Name(id="_", ctx=ast.Load()), args=args, keywords=keywords)


def _resolve_copied(func, site: _Site) -> str | None:
    """The defining name of a call used as an argument at this site, when the site already resolved it.

    Nested calls are reduced with the same file's imports. The resolver is attached by the collector."""
    resolve = getattr(site, "resolve", None)
    return resolve(func) if resolve else None


def _reduce(expr, scope: dict, resolve, spelling: dict, depth: int):
    """A copy of expr that uses only constants and base calls the probe can spell, or None.

    A name is copied only when this same function assigned it a copyable value before the call.
    A subscript is not a call and is not a value: the pull request's ``names[0]`` is not an argument."""
    if depth > 4 or expr is None:
        return None
    if isinstance(expr, ast.Constant) and isinstance(expr.value, (int, float, str, bool, type(None))):
        return ast.Constant(value=expr.value)
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, (ast.USub, ast.UAdd, ast.Not)):
        operand = _reduce(expr.operand, scope, resolve, spelling, depth + 1)
        return ast.UnaryOp(op=expr.op, operand=operand) if operand is not None else None
    if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
        elts = []
        for elt in expr.elts:
            got = _reduce(elt, scope, resolve, spelling, depth + 1)
            if got is None:
                return None
            elts.append(got)
        return type(expr)(elts=elts, ctx=ast.Load())
    if isinstance(expr, ast.Dict):
        keys, values = [], []
        for key, value in zip(expr.keys, expr.values):
            if key is None:
                return None
            got_key = _reduce(key, scope, resolve, spelling, depth + 1)
            got_value = _reduce(value, scope, resolve, spelling, depth + 1)
            if got_key is None or got_value is None:
                return None
            keys.append(got_key)
            values.append(got_value)
        return ast.Dict(keys=keys, values=values)
    if isinstance(expr, ast.Name):
        if expr.id not in scope:
            return None
        return _reduce(scope[expr.id], scope, resolve, spelling, depth + 1)
    if isinstance(expr, ast.Call):
        dotted = resolve(expr.func)
        callee = _spell(dotted, spelling) if dotted else None
        if callee is None:
            return None
        args = []
        for arg in expr.args:
            if isinstance(arg, ast.Starred):
                return None
            got = _reduce(arg, scope, resolve, spelling, depth + 1)
            if got is None:
                return None
            args.append(got)
        keywords = []
        for kw in expr.keywords:
            if kw.arg is None:
                return None
            got = _reduce(kw.value, scope, resolve, spelling, depth + 1)
            if got is None:
                return None
            keywords.append(ast.keyword(arg=kw.arg, value=got))
        return ast.Call(func=callee, args=args, keywords=keywords)
    return None


def _piece(name: str, pos_names: list[str], sites: list, spelling: dict):
    """(expression, where) for one required parameter, from the first base call that shows it."""
    index = pos_names.index(name) if name in pos_names else None
    for site in sites:
        expr = None
        if index is not None and index < len(site.call.args) and not isinstance(site.call.args[index], ast.Starred):
            # Only when this positional is not also given as a keyword later. The positional slot is enough.
            expr = site.call.args[index]
        for kw in site.call.keywords:
            if kw.arg == name:
                expr = kw.value
        if expr is None:
            continue
        got = _reduce(expr, site.scope, lambda func, site=site: _resolve_copied(func, site), spelling, 0)
        if got is not None:
            return got, f"{site.rel}:{site.lineno}"
    return None


def _collect_sites(base_root, targets: set[str]) -> dict[str, list]:
    """Real calls of these defining names, from the base tree only. At most a few per name."""
    found = {name: [] for name in targets}
    if not base_root or not targets:
        return found
    shorts = {name.split(".")[-1] for name in targets if name}
    files = []
    for root in _roots(Path(base_root)):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.endswith(".egg-info")
                           and not d.endswith(".dist-info")]
            for filename in filenames:
                if filename.endswith(".py"):
                    files.append((root, Path(dirpath) / filename))
    files.sort(key=lambda item: (0 if any(part in {"tests", "test", "testing"} for part in item[1].parts) else 1,
                                 str(item[1])))
    checker = _Checker(Path(base_root), skip_undefined=True)
    parsed = 0
    for root, path in files:
        if parsed >= _SITE_FILES or all(len(found[name]) >= _SITES_EACH for name in targets):
            break
        try:
            if path.stat().st_size > _SITE_BYTES:
                continue
            text = path.read_text(errors="replace")
        except OSError:
            continue
        if shorts and not any(short in text for short in shorts):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        module = _module_of(path, root)
        if not module:
            continue
        parsed += 1
        loc = locate(base_root, module)
        is_package = loc is not None and loc.kind == "package" and path.name == "__init__.py"
        try:
            rel = path.relative_to(base_root).as_posix()
        except ValueError:
            rel = path.name
        _harvest(tree, module, is_package, rel, checker, targets, found)

    return found


def _module_of(path: Path, root: Path) -> str | None:
    try:
        parts = list(path.relative_to(root).parts)
    except ValueError:
        return None
    if not parts:
        return None
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    else:
        return None
    if not parts or not all(part.isidentifier() for part in parts):
        return None
    return ".".join(parts)


def _harvest(tree, module: str, is_package: bool, rel: str, checker, targets: set[str], found: dict) -> None:
    symbols = _file_symbols(tree, module, is_package, checker)

    def resolve(func):
        return _resolve_in_file(func, symbols, checker)

    def consider(node: ast.Call, scope: dict) -> None:
        dotted = resolve(node.func)
        if dotted not in targets or len(found[dotted]) >= _SITES_EACH:
            return
        text = ast.unparse(node)
        if len(text) > 180:
            text = text[:177] + "..."
        site = _Site(dotted, rel, getattr(node, "lineno", 0) or 0, node, dict(scope), text)
        site.resolve = resolve
        found[dotted].append(site)

    def walk_body(body, scope: dict) -> None:
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in list(stmt.args.defaults) + [item for item in stmt.args.kw_defaults if item is not None]:
                    _consider_tree(default, scope, consider)
                walk_body(stmt.body, dict(scope))
                continue
            if isinstance(stmt, ast.ClassDef):
                for child in stmt.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        walk_body([child], dict(scope))
                    else:
                        walk_body([child], scope)
                continue
            if isinstance(stmt, ast.If):
                _consider_tree(stmt.test, scope, consider)
                walk_body(stmt.body, dict(scope))
                walk_body(stmt.orelse, dict(scope))
                continue
            if isinstance(stmt, (ast.For, ast.AsyncFor)):
                _consider_tree(stmt.iter, scope, consider)
                walk_body(stmt.body, dict(scope))
                walk_body(stmt.orelse, dict(scope))
                continue
            if isinstance(stmt, ast.While):
                _consider_tree(stmt.test, scope, consider)
                walk_body(stmt.body, dict(scope))
                walk_body(stmt.orelse, dict(scope))
                continue
            if isinstance(stmt, (ast.With, ast.AsyncWith)):
                for item in stmt.items:
                    _consider_tree(item.context_expr, scope, consider)
                walk_body(stmt.body, dict(scope))
                continue
            if isinstance(stmt, ast.Try):
                walk_body(stmt.body, dict(scope))
                for handler in stmt.handlers:
                    walk_body(handler.body, dict(scope))
                walk_body(stmt.orelse, dict(scope))
                walk_body(stmt.finalbody, dict(scope))
                continue
            _consider_tree(stmt, scope, consider)
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                scope[stmt.targets[0].id] = stmt.value
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
                scope[stmt.target.id] = stmt.value

    walk_body(tree.body, {})


def _consider_tree(node, scope: dict, consider) -> None:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            consider(child, scope)


def _file_symbols(tree, module: str, is_package: bool, checker) -> dict:
    """Local name -> ('def', dotted) or ('mod', module) or ('attr', 'module.name') for one base file."""
    symbols = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols[node.name] = ("def", f"{module}.{node.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                dotted = alias.name if alias.asname else alias.name.split(".")[0]
                symbols[local] = ("mod", dotted)
        elif isinstance(node, ast.ImportFrom):
            base = _absolute_module(module, is_package, node.level or 0, node.module)
            for alias in node.names:
                if alias.name == "*" or not base:
                    continue
                local = alias.asname or alias.name
                found = _lookup_def(checker, base, alias.name)
                if found:
                    symbols[local] = ("def", f"{found[1]}.{found[2].name}")
                else:
                    symbols[local] = ("attr", f"{base}.{alias.name}")
    return symbols


def _resolve_in_file(func, symbols: dict, checker) -> str | None:
    if isinstance(func, ast.Name):
        info = symbols.get(func.id)
        if not info:
            return None
        if info[0] == "def":
            return info[1]
        if info[0] == "attr":
            module, name = info[1].rsplit(".", 1)
            found = _lookup_def(checker, module, name)
            if found:
                return f"{found[1]}.{found[2].name}"
        return None
    parts = []
    cur = func
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name) or not parts:
        return None
    parts.reverse()
    info = symbols.get(cur.id)
    if not info:
        return None
    if info[0] == "mod":
        _sig, dotted = _resolve_named(checker, info[1], parts)
        return dotted
    if info[0] == "def" and len(parts) == 1:
        return info[1] + "." + parts[0]
    if info[0] == "attr":
        module, name = info[1].rsplit(".", 1)
        sig, dotted = _resolve_named(checker, module, [name, *parts])
        return dotted
    return None
