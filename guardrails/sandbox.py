"""Filesystem and network sandbox for untrusted code (bubblewrap, unprivileged user namespaces).

Every step that runs code from a PR or a package (installs and builds, pytest, coverage, probes, freezes, any start
of a venv Python) runs as

    bwrap --unshare-all [--share-net] --die-with-parent --new-session ...

with only these mounts:
  read-only   /usr (and the /bin, /lib, /lib64, /sbin links or binds), a minimal /etc (ld.so cache, alternatives,
              certificates, locale/time files; resolver files only when the network is allowed), the uv-managed
              Pythons at /opt/uv-python, and explicitly listed extra files (a wheel, a probe script, constraints)
  read-write  only the side's own work dirs, at their real paths (venv, checkout, temporary home, output dir)
  fresh       /tmp (tmpfs), /proc, /dev (minimal)
  install     the shared uv cache as a read-only lower layer at /opt/uv-cache with a private, discarded tmpfs layer on
              top (--overlay-src/--tmp-overlay): builds can use it but never write to the shared cache
Nothing else exists inside: no /home, no other worktrees, no agent data, no /sys. The network is shared only for
the install/build phase; test, coverage and probe phases have no network (only a loopback interface)."""
from __future__ import annotations

import functools
import os
import shutil
import subprocess
from pathlib import Path

INSIDE_PYTHON = "/opt/uv-python"
INSIDE_CACHE = "/opt/uv-cache"
ETC_ALWAYS = ("ld.so.cache", "ld.so.conf", "ld.so.conf.d", "alternatives", "ssl", "ca-certificates", "localtime",
              "timezone", "os-release", "protocols", "services", "mime.types")
ETC_NETWORK = ("resolv.conf", "hosts", "nsswitch.conf", "gai.conf", "host.conf")
UNAVAILABLE = "sandbox unavailable"


class SandboxError(RuntimeError):
    pass


_state = {"enabled": True}


def configure(enabled: bool) -> None:
    """enabled=False only with the explicit --unsafe-no-sandbox flag."""
    _state["enabled"] = enabled


def enabled() -> bool:
    return _state["enabled"]


def _root_links() -> list[str]:
    args = []
    for d in ("bin", "lib", "lib64", "lib32", "libx32", "sbin"):
        p = Path("/") / d
        if p.is_symlink():
            args += ["--symlink", os.readlink(p), f"/{d}"]
        elif p.is_dir():
            args += ["--ro-bind", str(p), f"/{d}"]
    return args


def _etc(network: bool) -> list[str]:
    args = []
    for name in ETC_ALWAYS + (ETC_NETWORK if network else ()):
        p = Path("/etc") / name
        if p.exists():
            args += ["--ro-bind", str(p), str(p)]
    return args


def _real(p: str | Path) -> str:
    return str(Path(p).resolve())


def bwrap_args(rw: list, ro: list = (), network: bool = False, cache: str | None = None,
               python_dir: str | None = None, cwd: str | Path | None = None, passwd: Path | None = None,
               binds: list = ()) -> list[str]:
    bw = shutil.which("bwrap")
    if not bw:
        raise SandboxError(f"{UNAVAILABLE}: bwrap not found")
    args = [bw, "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL", "--hostname", "sandbox"]
    if network:
        args.append("--share-net")
    args += ["--ro-bind", "/usr", "/usr", *_root_links(), *_etc(network),
             "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    if passwd:
        args += ["--ro-bind", str(passwd), "/etc/passwd", "--ro-bind", str(passwd.with_name("group")), "/etc/group"]
    if python_dir and Path(python_dir).is_dir():
        args += ["--ro-bind", _real(python_dir), INSIDE_PYTHON]
    if cache:
        Path(cache).mkdir(parents=True, exist_ok=True)
        args += ["--overlay-src", _real(cache), "--tmp-overlay", INSIDE_CACHE]
    for host, inside in binds:
        args += ["--ro-bind", _real(host), inside]
    for p in ro:
        args += ["--ro-bind", _real(p), _real(p)]
    for p in rw:
        Path(p).mkdir(parents=True, exist_ok=True)
        args += ["--bind", _real(p), _real(p)]
    if cwd:
        args += ["--chdir", _real(cwd)]
    return args


def _passwd(home: str) -> Path:
    """Synthetic /etc/passwd and /etc/group with one user (getpass/pwd lookups work; no real accounts leak)."""
    d = Path(home) / ".sandbox-etc"
    d.mkdir(parents=True, exist_ok=True)
    (d / "passwd").write_text(f"sandbox:x:{os.getuid()}:{os.getgid()}:sandbox:{home}:/bin/sh\n")
    (d / "group").write_text(f"sandbox:x:{os.getgid()}:\n")
    return d / "passwd"


def wrap(cmd: list, env: dict, rw: list, ro: list = (), network: bool = False, cwd=None) -> tuple[list, dict, None]:
    """(argv, env, cwd) to start cmd inside the sandbox. env is the allowlisted environment (base_env); its uv dirs
    are rewritten to the inside mount points and TMPDIR to a dir in the side's home (disk, not RAM). Installs
    (env has UV_CACHE_DIR) get the cache overlay. Without the sandbox (--unsafe-no-sandbox) cmd runs unchanged."""
    cmd = [str(c) for c in cmd]
    if not enabled():
        return cmd, env, cwd
    env = dict(env)
    home = env["HOME"]
    tmp = Path(home) / ".tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    env["TMPDIR"] = str(tmp)
    cache = env.pop("UV_CACHE_DIR", None)
    if cache and overlay_supported():
        env["UV_CACHE_DIR"] = INSIDE_CACHE
    elif cache:   # older bwrap without overlays: a private, empty cache per side (never the shared one)
        env["UV_CACHE_DIR"] = str(Path(home) / ".uv-cache")
        cache = None
    py = env.get("UV_PYTHON_INSTALL_DIR") or python_install_dir()
    if "UV_PYTHON_INSTALL_DIR" in env:
        env["UV_PYTHON_INSTALL_DIR"] = INSIDE_PYTHON
    binds = []
    if cmd and cmd[0] == "uv":   # uv itself: from /usr, or mounted read-only from wherever it is installed
        uv = shutil.which("uv")
        if not uv:
            raise SandboxError(f"{UNAVAILABLE}: uv not found")
        uv = _real(uv)
        if uv.startswith("/usr/"):
            cmd[0] = uv
        else:
            binds.append((uv, "/opt/uv-bin/uv"))
            cmd[0] = "/opt/uv-bin/uv"
    argv = bwrap_args([home, *rw], ro, network=network, cache=cache, python_dir=py, cwd=cwd, passwd=_passwd(home),
                      binds=binds)
    return argv + ["--", *cmd], env, None


@functools.lru_cache(maxsize=1)
def overlay_supported() -> bool:
    bw = shutil.which("bwrap")
    return bool(bw) and "--tmp-overlay" in subprocess.run([bw, "--help"], capture_output=True, text=True).stdout


def python_install_dir() -> str:
    from guardrails.isolation import _uv_dirs
    return _uv_dirs(dict(os.environ))["UV_PYTHON_INSTALL_DIR"]


@functools.lru_cache(maxsize=1)
def check() -> tuple[bool, str]:
    """Is the sandbox usable here? Starts a real one: no network, no /home, read-only /usr, writable bound dir."""
    if not shutil.which("bwrap"):
        return False, f"{UNAVAILABLE}: bwrap is not installed"
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        try:
            argv = bwrap_args([t], cwd=t)
        except SandboxError as e:
            return False, str(e)
        probe = "test ! -e /home && test ! -e /root && test -w . && ! test -w /usr && echo ok > f"
        try:
            p = subprocess.run(argv + ["--", "/bin/sh", "-c", probe], capture_output=True, text=True, timeout=30,
                               env={"PATH": "/usr/bin:/bin"})
        except (OSError, subprocess.TimeoutExpired) as e:
            return False, f"{UNAVAILABLE}: {e}"
        if p.returncode != 0 or not (Path(t) / "f").exists():
            return False, f"{UNAVAILABLE}: bwrap failed: {(p.stderr or p.stdout).strip()[:200]}"
    return True, "bubblewrap " + subprocess.run(["bwrap", "--version"], capture_output=True, text=True).stdout.split()[-1]
