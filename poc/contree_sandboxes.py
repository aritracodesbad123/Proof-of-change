"""Nebius Token Factory Sandboxes (Contree) for probe and pytest dual-runs.

--sandbox-backend local    bubblewrap via guardrails/sandbox.py (default)
--sandbox-backend contree  Contree when NEBIUS_API_KEY + NEBIUS_PROJECT_ID are set and contree-sdk is installed

Secrets never enter Contree shell env. Concurrent ops are capped at CONTREE_MAX_OPS (default 40).
"""
from __future__ import annotations

import os
import re
import shlex
import threading
from pathlib import Path
from typing import Any, Callable

KEY_ENV = "NEBIUS_API_KEY"
PROJECT_ENV = "NEBIUS_PROJECT_ID"
REQUIRE_ENV = "POC_REQUIRE_CONTREE"
MAX_OPS = int(os.environ.get("CONTREE_MAX_OPS", "40"))
BACKENDS = ("local", "contree")
BASE_IMAGE = os.environ.get("POC_CONTREE_BASE_IMAGE", "docker.io/library/python:3.12-slim-bookworm")
SDK_VERSION = "0.3.6"


def image_python(image: str | None = None) -> str:
    """'X.Y' read from the Contree base image tag (for example python:3.12-slim), or '' when the tag names none.

    Version selection for a Contree check uses this, not the Pythons on the machine that runs the orchestrator."""
    import re
    tag = (image or BASE_IMAGE).rsplit("/", 1)[-1]
    if not tag.startswith("python:"):
        return ""
    m = re.search(r":(\d+)\.(\d+)(?:[.-]|$)", tag)
    return f"{m.group(1)}.{m.group(2)}" if m else ""

_sem = threading.Semaphore(MAX_OPS)
_state: dict[str, Any] = {"backend": "local", "note": "local bubblewrap", "session": None}


class ContreeError(RuntimeError):
    """Contree failed; message must never contain API keys.

    exit_code and stderr_tail (redacted) describe a failed sandbox command; auth is True only when the
    Contree API itself refused the credentials."""

    def __init__(self, msg: str, *, exit_code=None, stderr_tail: str = "", auth: bool = False):
        super().__init__(msg)
        self.exit_code = exit_code
        self.stderr_tail = stderr_tail
        self.auth = auth


AUTH_ERROR_NAMES = ("forbidden", "unauthorized", "unauthorised", "authentication", "permissiondenied")
TAIL_CHARS = 1500


def redact(text: str, env: dict | None = None) -> str:
    """Remove the Nebius key and project id, bearer tokens, every secret demo_helper.redact knows, GitHub tokens
    (ghp_/gho_/ghu_/ghs_/ghr_/github_pat_), sk- style keys, passwords in URLs (scheme://user:pw@host),
    Authorization: Basic values and plain password=/passwd=/pwd=/token= values."""
    import re
    env = os.environ if env is None else env
    out = (text or "").replace("\x00", "")
    for k in (KEY_ENV, PROJECT_ENV):
        v = env.get(k)
        if v and str(v).strip():
            out = out.replace(str(v), f"<{k} redacted>")
    out = re.sub(r"(?i)(bearer\s+)\S+", r"\1<redacted>", out)
    out = re.sub(r"(?i)(authorization:\s*basic\s+)\S+", r"\1<redacted>", out)
    # Hide key=value secrets first (a quoted value whole, else up to whitespace, & or a quote) and keep them out
    # of demo_helper.redact's broader token= rule, which would also eat what follows the &, by parking them
    # behind per-call random markers. NUL bytes are stripped from the input so no marker can be forged.
    import uuid
    tag = uuid.uuid4().hex
    parked: list[str] = []

    def _park(m):
        q = m.group(2) or ""
        parked.append(f"{m.group(1)}={q}<redacted>{q}")
        return f"\x00{tag}:{len(parked) - 1}\x00"

    out = re.sub(r"""(?i)\b(password|passwd|pwd|token)=(?:(['"])[^'"]*\2|[^\s&'"]+)""", _park, out)
    try:
        from poc import demo_helper
    except ImportError:  # pragma: no cover - script run from inside poc/
        import demo_helper  # type: ignore
    out = demo_helper.redact(out, env)
    out = re.sub("\x00" + tag + r":(\d+)\x00",
                 lambda m: parked[int(m.group(1))] if int(m.group(1)) < len(parked) else "<redacted>", out)
    out = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{8,})", "<redacted>", out)
    out = re.sub(r"\bsk-[A-Za-z0-9_\-]{8,}", "<redacted>", out)
    out = re.sub(r"(?i)\b([a-z][a-z0-9+.\-]*://[^\s:/@]+:)[^\s@/]+@", r"\1***@", out)
    return out


def tail(text: str, n: int = TAIL_CHARS) -> str:
    text = redact(text or "").strip()
    return text if len(text) <= n else "..." + text[-n:]


def is_auth_error(exc: BaseException) -> bool:
    """True only for an API auth refusal (by exception class name or HTTP 401/403 status)."""
    name = type(exc).__name__.lower()
    if any(w in name for w in AUTH_ERROR_NAMES):
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    return status in (401, 403)


def bash_wrapped(shell: str) -> str:
    """POSIX sh script that runs shell under bash when present (so set -o pipefail works), else under sh with
    pipefail removed. Contree runs commands with /bin/sh, which is dash on Debian images."""
    fallback = shell.replace("set -euo pipefail", "set -eu").replace("set -o pipefail", ":")
    return (f"if command -v bash >/dev/null 2>&1; then\n  exec bash -c {shlex.quote(shell)}\nfi\n"
            f"{fallback}")


def setup_failure(what: str, raw: dict) -> ContreeError:
    code = raw.get("exit_code")
    err = tail(raw.get("stderr") or "") or tail(raw.get("stdout") or "")
    msg = f"{what} failed (exit {code})"
    if err:
        msg += f"; last error output: {err[-300:]}"
    return ContreeError(msg, exit_code=code, stderr_tail=err)


def select(name: str, env: dict | None = None) -> tuple[str, str]:
    """Return (backend, note). contree without credentials/SDK falls back to local unless POC_REQUIRE_CONTREE=1."""
    env = os.environ if env is None else env
    if name == "local":
        _state.update(backend="local", note="local bubblewrap", session=None)
        return "local", _state["note"]
    if name != "contree":
        raise ValueError(f"unknown sandbox backend {name!r}; one of {BACKENDS}")

    key = env.get(KEY_ENV)
    project = env.get(PROJECT_ENV)
    missing = []
    if key is None or str(key).strip() == "":
        missing.append(KEY_ENV)
    if project is None or str(project).strip() == "":
        missing.append(PROJECT_ENV)
    if missing:
        note = f"contree requested but {' and '.join(missing)} missing/empty: using local bubblewrap"
        if str(env.get(REQUIRE_ENV) or "").strip().lower() in ("1", "true", "yes"):
            raise ContreeError(
                f"STOPPED: --sandbox-backend contree requires {' and '.join(missing)}. "
                "Set them and run again, or pass --sandbox-backend local."
            )
        _state.update(backend="local", note=note, session=None)
        return "local", note

    try:
        import contree_sdk  # noqa: F401
    except ImportError:
        note = ("contree requested but contree-sdk is not installed: using local bubblewrap "
                "(pip install -e '.[contree]')")
        if str(env.get(REQUIRE_ENV) or "").strip().lower() in ("1", "true", "yes"):
            raise ContreeError(
                "STOPPED: contree-sdk is not installed. pip install -e '.[contree]', "
                "or pass --sandbox-backend local."
            )
        _state.update(backend="local", note=note, session=None)
        return "local", note

    note = f"contree (Token Factory Sandboxes, sdk {SDK_VERSION})"
    _state.update(backend="contree", note=note)
    return "contree", note


def backend() -> str:
    return _state["backend"]


def note() -> str:
    return _state["note"]


def with_slot(fn: Callable[[], Any]) -> Any:
    with _sem:
        return fn()


def _text(val) -> str:
    if val is None:
        return ""
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", "replace")
    return str(val)


class ContreeSession:
    """One PR's Contree checkpoints (main + PR) and disposable runs."""

    def __init__(self, *, base_image: str = BASE_IMAGE, runner: Callable | None = None):
        self.base_image = base_image
        self.main_uuid: str | None = None
        self.pr_uuid: str | None = None
        # runner(shell, disposable, image_ref|None, timeout, files) -> {exit_code,stdout,stderr,uuid}
        self._runner = runner
        self._client = None

    def describe(self) -> dict:
        return {"main_uuid": self.main_uuid, "pr_uuid": self.pr_uuid, "max_ops": MAX_OPS,
                "sdk": SDK_VERSION, "base_image": self.base_image}

    def _client_sync(self):
        if self._client is not None:
            return self._client
        try:
            from contree_sdk import ContreeSync
        except ImportError as e:
            raise ContreeError("contree-sdk is not installed; pip install -e '.[contree]'") from e
        self._client = ContreeSync()
        return self._client

    def _run_on(self, image_ref: str | None, shell: str, *, disposable: bool, timeout: int,
                files: dict | None = None) -> dict:
        if self._runner is not None:
            return self._runner(shell, disposable, image_ref, timeout, files)

        client = self._client_sync()
        try:
            if image_ref:
                img = client.images.use(image_ref, strict=True)
            else:
                img = client.images.oci(self.base_image)
            result = img.run(shell=bash_wrapped(shell), disposable=disposable, timeout=timeout,
                             files=files or None).wait()
        except ContreeError:
            raise
        except Exception as e:  # noqa: BLE001 — never leak tokens from SDK messages
            if is_auth_error(e):
                raise ContreeError(f"Contree API refused access ({type(e).__name__})", auth=True) from None
            raise ContreeError(f"contree request failed: {type(e).__name__}") from None

        uuid = getattr(result, "uuid", None)
        return {
            "exit_code": getattr(result, "exit_code", None),
            "stdout": _text(getattr(result, "stdout", None)),
            "stderr": _text(getattr(result, "stderr", None)),
            "uuid": str(uuid) if uuid is not None else None,
        }

    def run_op(self, side: str, shell: str, *, disposable: bool = True, timeout: int = 600,
               files: dict | None = None) -> dict:
        """Run shell on main or pr checkpoint (or base image if building a checkpoint)."""
        if side not in ("main", "pr", "base"):
            raise ContreeError(f"unknown side {side!r}")
        uuid = None if side == "base" else (self.main_uuid if side == "main" else self.pr_uuid)
        if disposable and side != "base" and not uuid:
            raise ContreeError(f"no {side} checkpoint yet; call checkpoint_main / fork_pr first")
        return with_slot(lambda: self._run_on(uuid, shell, disposable=disposable, timeout=timeout, files=files))

    def checkpoint_main(self, install_shell: str, *, timeout: int = 1800) -> dict:
        """Build/save main checkpoint from BASE_IMAGE + install_shell (disposable=False)."""
        shell = f"set -euo pipefail\nmkdir -p /work\ncd /work\n{install_shell}"
        raw = self.run_op("base", shell, disposable=False, timeout=timeout)
        if raw.get("exit_code") != 0:
            raise setup_failure("main checkpoint install", raw)
        uuid = raw.get("uuid")
        if not uuid:
            raise ContreeError("main checkpoint returned no reusable image id")
        self.main_uuid = str(uuid)
        return {"backend": "contree", "kind": "main", "uuid": self.main_uuid, "disposable": False}

    def fork_pr(self, install_shell: str, *, timeout: int = 1800) -> dict:
        """Fork from main checkpoint, apply PR install, save PR checkpoint."""
        if not self.main_uuid:
            raise ContreeError("fork_pr needs checkpoint_main first")
        shell = f"set -euo pipefail\ncd /work 2>/dev/null || {{ mkdir -p /work && cd /work; }}\n{install_shell}"
        raw = self.run_op("main", shell, disposable=False, timeout=timeout)
        if raw.get("exit_code") != 0:
            raise setup_failure("PR checkpoint install", raw)
        uuid = raw.get("uuid")
        if not uuid:
            # filesystem may be unchanged; reuse main as starting point only if install was a no-op — refuse
            raise ContreeError("PR checkpoint returned no reusable image id")
        self.pr_uuid = str(uuid)
        return {"backend": "contree", "kind": "pr", "uuid": self.pr_uuid, "from": self.main_uuid,
                "disposable": False}

    def run_argv(self, side: str, argv: list, *, timeout: int = 600, cwd: str = "/work/src",
                 files: dict | None = None) -> dict:
        """Run argv on a side checkpoint; returns exit_code/stdout/stderr like a local subprocess."""
        cmd = " ".join(shlex.quote(str(a)) for a in argv)
        shell = f"set -euo pipefail\ncd {shlex.quote(cwd)}\n{cmd}"
        return self.run_op(side, shell, disposable=True, timeout=timeout, files=files)


_PY_VERSION_OUT = re.compile(r"^Python (\d+\.\d+(?:\.\d+)?)((?:a|b|rc)\d+)?(\+\S*)?\s*$")


def parse_python_version(raw: dict | None) -> str:
    """The full version from a `python --version` result, pre-release (a/b/rc) and local (+...) tags kept,
    for example '3.13.0rc1' or '3.12.7+'. '' when the run failed or printed something else."""
    if not isinstance(raw, dict) or raw.get("exit_code") != 0:
        return ""
    text = ((raw.get("stdout") or "") + "\n" + (raw.get("stderr") or "")).strip().splitlines()
    for line in text:
        m = _PY_VERSION_OUT.match(line.strip())
        if m:
            return "".join(g for g in m.groups() if g is not None)
    return ""


def split_python_version(version: str) -> tuple[tuple[int, ...], str, str] | None:
    """(release numbers, pre-release tag, local tag) of a parsed version, or None when it is not one."""
    m = re.fullmatch(r"(\d+\.\d+(?:\.\d+)?)((?:a|b|rc)\d+)?(\+\S*)?", version or "")
    if not m:
        return None
    return tuple(int(x) for x in m.group(1).split(".")), m.group(2) or "", m.group(3) or ""


_RP_CLAUSE = re.compile(r"^(~=|==|!=|>=|<=|>|<)\s*(\d+(?:\.\d+)*)(\.\*)?$")


def parse_requires_python(text: str) -> list[tuple[str, tuple[int, ...], bool]] | None:
    """Clauses of a requires-python string as (op, version, wildcard), all ANDed. None when any part is unreadable.

    Stdlib only. Supports ==, !=, >=, <=, >, <, ~= and ==X.* / !=X.*. Nothing is dropped: one bad clause makes the
    whole string unreadable."""
    parts = [p.strip() for p in (text or "").split(",")]
    if not parts or any(not p for p in parts):
        return None
    out = []
    for part in parts:
        m = _RP_CLAUSE.match(part)
        if not m:
            return None
        op, ver, star = m.group(1), tuple(int(x) for x in m.group(2).split(".")), bool(m.group(3))
        if star and op not in ("==", "!="):
            return None
        if op == "~=" and len(ver) < 2:
            return None
        out.append((op, ver, star))
    return out


def _pad(v: tuple[int, ...], n: int) -> tuple[int, ...]:
    return v + (0,) * (n - len(v))


def requires_python_ok(full: tuple[int, ...], clauses) -> bool:
    """True when the full version (major, minor, micro) meets every clause."""
    for op, ver, star in clauses:
        if star:
            hit = full[:len(ver)] == ver
            if (op == "==") != hit:
                return False
            continue
        n = max(len(full), len(ver))
        a, b = _pad(full, n), _pad(ver, n)
        if op == "~=":
            ok = a >= b and full[:len(ver) - 1] == ver[:-1]
        else:
            ok = {"==": a == b, "!=": a != b, ">=": a >= b, "<=": a <= b, ">": a > b, "<": a < b}[op]
        if not ok:
            return False
    return True


def side_pythons(sess: "ContreeSession", specs: list[str], *, timeout: int = 120) -> dict:
    """Which Python actually runs on each side's Contree checkpoint, checked against the project's requires-python.

    Runs `python --version` from the main and PR checkpoints (the same place the tests run). Each side whose
    version cannot be read, or does not satisfy requires-python, adds a problem. A non-empty `problems` list means
    the check must not pass as a normal result. Both sides must also report the exact same full version."""
    texts = [s.strip() for s in specs or [] if isinstance(s, str) and s.strip()]
    out: dict = {"requires_python": texts, "requires_python_found": bool(texts), "main": "", "pr": "",
                 "problems": []}
    spec_sets = []
    for text in texts:
        clauses = parse_requires_python(text)  # every clause kept, e.g. '>=3.8,<4' keeps '<4'
        if clauses is None:
            out["problems"].append(f"requires-python could not be read: {text!r}")
        else:
            spec_sets.append(clauses)
    spec_ok = len(spec_sets) == len(texts)
    for side in ("main", "pr"):
        try:
            raw = sess.run_argv(side, ["python", "--version"], timeout=timeout, cwd="/work")
        except ContreeError as e:
            raw = {"exit_code": None, "stderr": f"{type(e).__name__}"}
        version = parse_python_version(raw)
        out[side] = version
        if not version:
            out["problems"].append(f"{side}: the Python version inside Contree could not be read")
            continue
        parts = split_python_version(version)
        if parts is None:
            out["problems"].append(f"{side}: the Python version inside Contree could not be read")
            continue
        if parts[1]:
            out["problems"].append(f"{side}: Contree ran a pre-release Python ({version})")
        if not spec_ok:
            continue
        full = parts[0]
        if not all(requires_python_ok(full, clauses) for clauses in spec_sets):
            out["problems"].append(f"{side}: Contree ran Python {version}, which does not satisfy requires-python "
                                   f"{', '.join(texts)}")
    if out["main"] and out["pr"] and out["main"] != out["pr"]:
        out["problems"].append(f"main ran {out['main']}, PR ran {out['pr']}")
    return out


def new_session(**kw) -> ContreeSession:
    sess = ContreeSession(**kw)
    _state["session"] = sess
    return sess


def session() -> ContreeSession | None:
    return _state.get("session")


def clear_session() -> None:
    _state["session"] = None


DEPS_ONLY_SHELL = (
    "{ echo 'Auto-fix: the project could not be built as a package, so only the dependencies it declares are installed';"
    " python -m pip install -q uv==0.13.1 2>/dev/null || true;"
    " PYX=\"$(python -c 'import sys; print(sys.executable)')\"; PFX=\"$(python -c 'import sys; print(sys.prefix)')\";"
    " if [ -f pyproject.toml ] && [ -f uv.lock ]; then UV_PROJECT_ENVIRONMENT=\"$PFX\" python -m uv sync -q"
    " --no-install-project --frozen -p \"$PYX\";"
    " elif [ -f pyproject.toml ]; then UV_PROJECT_ENVIRONMENT=\"$PFX\" python -m uv sync -q --no-install-project -p \"$PYX\";"
    " else for f in requirements*.txt; do if [ -f \"$f\" ]; then python -m pip install -q -r \"$f\"; fi; done; fi"
    " && CHG=\"$(git status --porcelain --untracked-files=all --ignored=no | grep -v ' .poc-declared-deps.txt$' || true)\""
    " && if [ -n \"$CHG\" ]; then echo \"setup problem: the dependency install changed the checked-out code: $CHG\"; exit 1; fi"
    " && SP=\"$(python -c 'import sysconfig; print(sysconfig.get_paths()[\"purelib\"])')\""
    " && rm -f \"$SP/poc-project-path.pth\" && echo /work/src > \"$SP/poc-project-path.pth\"; }"
)


def install_shell_source(repo: str, sha: str, extra: str = "", deps_only_fallback: bool = False) -> str:
    """Clone a public GitHub SHA into /work/src and pip-install editable + pytest (source-pair style).

    extra is the same shell on both sides (system packages and plan requirements). Empty leaves the
    original install unchanged.
    """
    # slim image needs git; network is available during checkpoint builds
    shell = (
        "export DEBIAN_FRONTEND=noninteractive\n"
        "(command -v git >/dev/null || (apt-get update -qq && apt-get install -y -qq git >/dev/null))\n"
        "python -m pip install -q --upgrade pip\n"
        "rm -rf /work/src\n"
        "mkdir -p /work/src && cd /work/src\n"
        "git init -q\n"
        f"git remote add origin https://github.com/{repo}.git\n"
        f"git fetch -q --depth 1 origin {sha}\n"
        "git checkout -q FETCH_HEAD\n"
        "python -m pip install -q -e '.[dev]' 2>/dev/null "
        "|| python -m pip install -q -e '.[test]' 2>/dev/null "
        "|| python -m pip install -q -e '.[tests]' 2>/dev/null "
        "|| python -m pip install -q -e ." + (" \\\n|| " + DEPS_ONLY_SHELL if deps_only_fallback else "") + "\n"
        "python -m pip install -q pytest pytest-timeout pytest-xdist coverage pytest-cov\n"
    )
    extra = (extra or "").strip()
    if not extra:
        return shell
    needle = "python -m pip install -q -e '.[dev]'"
    return shell.replace(needle, extra + "\n" + needle, 1)


def prepare_source_pair(repo: str, main_sha: str, pr_sha: str, *, timeout: int = 1800,
                        runner: Callable | None = None, extra_shell: str = "",
                        deps_only_fallback: bool = False) -> ContreeSession:
    """Build main + PR Contree checkpoints for a source-pair style PR.

    extra_shell is applied to both SHAs. Empty keeps the default install shell.
    """
    sess = new_session(runner=runner) if runner is not None else new_session()
    sess.checkpoint_main(install_shell_source(repo, main_sha, extra_shell, deps_only_fallback), timeout=timeout)
    sess.fork_pr(install_shell_source(repo, pr_sha, extra_shell, deps_only_fallback), timeout=timeout)
    return sess


def smoke(env: dict | None = None) -> dict:
    """Live Contree smoke: write a file, save checkpoint, read it back. Needs credentials + SDK."""
    env = os.environ if env is None else env
    be, n = select("contree", env)
    if be != "contree":
        return {"ok": False, "skipped": True, "note": n}
    sess = ContreeSession()
    prep = sess.checkpoint_main("printf 'ready\\n' > /work/status.txt", timeout=120)
    got = sess.run_op("main", "cat /work/status.txt", disposable=True, timeout=60)
    ok = got.get("exit_code") == 0 and "ready" in (got.get("stdout") or "")
    return {"ok": ok, "checkpoint": prep, "read": got, "note": n}


# Marker helpers (local filesystem) — used when Contree session is not live
def checkpoint_main(base_sha: str, work: Path) -> dict:
    sess = session()
    if sess and backend() == "contree" and sess.main_uuid:
        return {"backend": "contree", "kind": "main", "sha": base_sha, "uuid": sess.main_uuid, "disposable": False}
    marker = work / f"checkpoint-main-{base_sha[:12]}"
    marker.mkdir(parents=True, exist_ok=True)
    return {"backend": backend(), "kind": "main", "sha": base_sha, "path": str(marker), "disposable": False}


def fork_pr(main_cp: dict, head_sha: str, work: Path) -> dict:
    sess = session()
    if sess and backend() == "contree" and sess.pr_uuid:
        return {"backend": "contree", "kind": "pr", "sha": head_sha, "uuid": sess.pr_uuid,
                "from": sess.main_uuid or main_cp.get("uuid"), "disposable": False}
    marker = work / f"checkpoint-pr-{head_sha[:12]}"
    marker.mkdir(parents=True, exist_ok=True)
    return {"backend": backend(), "kind": "pr", "sha": head_sha, "path": str(marker),
            "from": main_cp.get("path") or main_cp.get("uuid"), "disposable": True}


if __name__ == "__main__":
    # ponytail: assert-based self-check for select() fallback (no live Contree)
    be, n = select("contree", env={})
    assert be == "local" and KEY_ENV in n and PROJECT_ENV in n, (be, n)
    be, n = select("contree", env={KEY_ENV: "x", PROJECT_ENV: "y"})
    # SDK may or may not be installed in the invoking interpreter
    assert be in ("local", "contree"), be
    print("contree_sandboxes self-check ok")
