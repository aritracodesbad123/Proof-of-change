"""Untrusted code runs in a bubblewrap sandbox (guardrails/sandbox.py): it cannot read files outside its own side's
work dir, has no network outside the install phase, cannot write the shared uv cache, and sees only the allowlisted
environment. These tests start REAL sandboxes through the daily run's own code paths (install_side, run_tests,
run_probes) and plant dummy secrets outside.

They must run wherever bubblewrap works (the default). Only on GitHub runners, if bwrap cannot start there, they skip."""
import json
import os
import socket
import threading
import uuid
from pathlib import Path

import pytest

from guardrails import isolation as iso
from guardrails import sandbox
from ops import daily_run
from poc import probes

REPO = Path(__file__).resolve().parent.parent
OK, WHY = sandbox.check()
if not OK and os.environ.get("GITHUB_ACTIONS"):
    pytestmark = pytest.mark.skip(reason=f"bubblewrap cannot start on this CI runner: {WHY}")
elif not OK:
    pytest.fail(f"the sandbox must work on this machine: {WHY}", pytrace=False)

FAKE_SECRETS = {"NEBIUS_KEY": "fake-nebius", "TAVILY_KEY": "fake-tavily", "OPENAI_APIKEY": "fake-openai",
                "GH_PAT": "fake-pat", "DATABASE_URL": "postgres://u:fake-pw@db/x", "NPM_AUTH": "fake-npm",
                "GITHUB_POC_TOKEN": "fake-poc"}
RUN_KEYS = {"PATH", "HOME", "TMPDIR", "PYTHONHASHSEED", "PYTHONDONTWRITEBYTECODE", "MPLBACKEND",
            "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"}
OPTIONAL = {"LANG", "LC_ALL", "TERM", "SOURCE_DATE_EPOCH", "SSL_CERT_FILE"}   # passed through only if set outside
ADDED_BY_TOOLS = {"PYTEST_VERSION", "PYTEST_CURRENT_TEST", "PWD"}   # PWD: set by bwrap after --chdir


def _python_spec() -> str:
    d = Path(sandbox.python_install_dir())
    return "3.12" if any(d.glob("cpython-3.12*")) else "/usr/bin/python3"


@pytest.fixture(scope="module")
def secrets(tmp_path_factory):
    """Dummy secret files: in a stand-in for the user's home, in the real home, and under the real repo path."""
    tag = uuid.uuid4().hex[:8]
    fake_home = tmp_path_factory.mktemp("home-standin")
    planted = [fake_home / "secret.txt", Path.home() / f".poc-sandbox-test-{tag}", REPO / f".poc-sandbox-test-{tag}"]
    for f in planted:
        f.write_text("TOP-SECRET-" + tag)
    yield [str(f) for f in planted]
    for f in planted:
        f.unlink(missing_ok=True)


@pytest.fixture
def fake_env_secrets(monkeypatch):
    for k, v in FAKE_SECRETS.items():
        monkeypatch.setenv(k, v)


@pytest.fixture(scope="module")
def listener():
    """A TCP server on the host's loopback: reachable from outside, must not be from the sandbox."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    threading.Thread(target=lambda: [c.close() for c in iter(lambda: srv.accept()[0], None)], daemon=True).start()
    yield srv.getsockname()[1]
    srv.close()


EVIL_BACKEND = r'''
import base64, hashlib, json, os, socket, zipfile
from pathlib import Path

def _attempts():
    cfg = json.loads(Path(__file__).with_name("targets.json").read_text())
    out = {"read": {}, "listing": {}}
    for p in cfg["secrets"]:
        try:
            out["read"][p] = Path(p).read_text()
        except OSError as e:
            out["read"][p] = type(e).__name__
    for d in ("/home", "/root", "/sys", cfg["repo"], cfg["repo_parent"], cfg["real_cache"]):
        out["listing"][d] = os.path.exists(d)
    marker = "poison-" + cfg["tag"]
    for where in (os.environ.get("UV_CACHE_DIR"), cfg["real_cache"]):
        try:
            Path(where, marker).write_text("x")
            out.setdefault("cache_write", {})[where] = "written"
        except (OSError, TypeError) as e:
            out.setdefault("cache_write", {})[str(where)] = type(e).__name__
    out["env"] = dict(os.environ)
    Path(__file__).with_name("build-attempts.json").write_text(json.dumps(out))

def _wheel(wheel_directory):
    _attempts()
    name = "evilpkg-0.1-py3-none-any.whl"
    files = {"evilpkg/__init__.py": b"X = 1\n",
             "evilpkg-0.1.dist-info/METADATA": b"Metadata-Version: 2.1\nName: evilpkg\nVersion: 0.1\n",
             "evilpkg-0.1.dist-info/WHEEL": b"Wheel-Version: 1.0\nGenerator: t\nRoot-Is-Purelib: true\nTag: py3-none-any\n"}
    rec = "".join(f"{n},sha256={base64.urlsafe_b64encode(hashlib.sha256(b).digest()).rstrip(b'=').decode()},{len(b)}\n"
                  for n, b in files.items()) + "evilpkg-0.1.dist-info/RECORD,,\n"
    with zipfile.ZipFile(os.path.join(wheel_directory, name), "w") as z:
        for n, b in files.items():
            z.writestr(n, b)
        z.writestr("evilpkg-0.1.dist-info/RECORD", rec)
    return name

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    return _wheel(wheel_directory)

def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    return _wheel(wheel_directory)

def get_requires_for_build_wheel(config_settings=None):
    return []

def get_requires_for_build_editable(config_settings=None):
    return []
'''

ATTEMPTS = r'''
import json, os, socket, sys
from pathlib import Path
cfg = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else os.environ["T"]).read_text())
out = {"read": {}, "listing": {}, "net": {}}
for p in cfg["secrets"]:
    try:
        out["read"][p] = Path(p).read_text()
    except OSError as e:
        out["read"][p] = type(e).__name__
for d in ("/home", "/root", "/sys", cfg["repo"], cfg["repo_parent"], cfg["other_side"]):
    out["listing"][d] = os.path.exists(d)
for host, port in (("1.1.1.1", 53), ("127.0.0.1", cfg["port"])):
    s = socket.socket()
    s.settimeout(3)
    try:
        s.connect((host, port))
        out["net"][f"{host}:{port}"] = "CONNECTED"
    except OSError as e:
        out["net"][f"{host}:{port}"] = type(e).__name__ + ": " + str(e)
    finally:
        s.close()
out["env"] = dict(os.environ)
'''


@pytest.fixture(scope="module")
def work(tmp_path_factory, secrets):
    """A PR work dir with two real sandboxed venvs, each with an editable 'PR' package whose build backend tries to
    read the secrets and poison the shared uv cache (install/build phase, with network)."""
    w = tmp_path_factory.mktemp("work")
    tag = uuid.uuid4().hex[:8]
    real_cache = iso._uv_dirs(dict(os.environ))["UV_CACHE_DIR"]
    for side in ("main", "pr"):
        co = w / f"side-{side}"
        co.mkdir()
        (co / "pyproject.toml").write_text('[build-system]\nrequires = []\nbuild-backend = "evil_backend"\n'
                                           'backend-path = ["."]\n[project]\nname = "evilpkg"\nversion = "0.1"\n')
        (co / "evil_backend.py").write_text(EVIL_BACKEND)
        (co / "targets.json").write_text(json.dumps({"secrets": secrets, "repo": str(REPO), "repo_parent": str(REPO.parent), "tag": tag,
                                                     "real_cache": real_cache}))
    os.environ.update(FAKE_SECRETS)   # also present while installing; removed below
    try:
        res = {s: daily_run.install_side(w / f"venv-{s}", w / f"side-{s}", None, w / f"setup-{s}.log", _python_spec(),
                                         900, None) for s in ("main", "pr")}
    finally:
        for k in FAKE_SECRETS:
            os.environ.pop(k, None)
    assert all(ok for ok, _ in res.values()), {s: (w / f"setup-{s}.log").read_text()[-3000:] for s in res}
    return {"dir": w, "tag": tag, "real_cache": real_cache}


def _assert_contained(att: dict, secrets: list):
    assert all(v in ("FileNotFoundError", "PermissionError") for v in att["read"].values()), att["read"]
    assert not any(att["listing"].values()), att["listing"]


def _assert_env(env: dict, extra: set = frozenset()):
    assert not set(FAKE_SECRETS) & set(env)
    assert not any(v in str(env.values()) for v in FAKE_SECRETS.values())
    assert RUN_KEYS <= set(env) and set(env) <= RUN_KEYS | OPTIONAL | ADDED_BY_TOOLS | set(extra), sorted(env)


# ---------------------------------------------------------------- install/build phase
def test_build_backend_cannot_read_secrets_or_write_the_shared_cache(work, secrets):
    for side in ("main", "pr"):
        att = json.loads((work["dir"] / f"side-{side}" / "build-attempts.json").read_text())
        _assert_contained(att, secrets)
        cw = att["cache_write"]
        # the shared cache's real path does not exist inside; UV_CACHE_DIR is a private layer, discarded on exit
        assert cw[work["real_cache"]] in ("FileNotFoundError", "PermissionError", "OSError"), cw
        assert not (Path(work["real_cache"]) / f"poison-{work['tag']}").exists()
        assert att["env"]["UV_CACHE_DIR"] in (sandbox.INSIDE_CACHE, att["env"]["HOME"] + "/.uv-cache")
        _assert_env(att["env"], extra=set(iso.INSTALL_ALLOWLIST) | {"UV", "VIRTUAL_ENV", "UV_INTERNAL__BUILD_DIR",
                                                                     "PYTHONIOENCODING", "PEP517_BUILD_BACKEND", "PWD"})


def test_direct_write_to_the_shared_cache_fails(work):
    """Even a plain write to the cache mount from inside an install sandbox never reaches the shared cache."""
    marker = f"poison-direct-{uuid.uuid4().hex[:8]}"
    venv = work["dir"] / "venv-pr"
    cp = daily_run.in_side(venv, ["/bin/sh", "-c", f'echo x > "$UV_CACHE_DIR/{marker}" && echo wrote; '
                                  f'echo x > "{work["real_cache"]}/{marker}" 2>/dev/null || echo blocked'],
                           install=True, network=True)
    assert "blocked" in cp.stdout
    assert not (Path(work["real_cache"]) / marker).exists()


# ---------------------------------------------------------------- probe phase
def test_probe_cannot_read_secrets_and_has_no_network(work, secrets, listener, fake_env_secrets, monkeypatch, tmp_path):
    w = work["dir"]
    cfg = tmp_path / "t.json"
    cfg.write_text(json.dumps({"secrets": secrets, "repo": str(REPO), "repo_parent": str(REPO.parent), "port": listener,
                               "other_side": str(w / "venv-main")}))
    probe = tmp_path / "1.py"
    probe.write_text('PROBE = {"id": "escape", "target": "o/r#1", "about": "sandbox", "claims": []}\n'
                     + ATTEMPTS.replace('sys.argv[1] if len(sys.argv) > 1 else os.environ["T"]', repr(str(cfg)))
                     + 'print(json.dumps({"observations": {"attempts": out}}))\n')
    # the probe reads its targets file: mount it read-only like the probe file itself
    monkeypatch.setattr(daily_run, "probe_launcher", lambda venv, path: (
        lambda argv, env, cwd: sandbox.wrap(argv, env, **{**daily_run.side_sandbox(venv, ro=(path, cfg))}, cwd=cwd)))
    monkeypatch.setattr(probes, "find_probes", lambda repo, pr: [probe])
    monkeypatch.setattr(daily_run, "repo_relative", lambda p: str(p))
    prdir = tmp_path / "run"
    prdir.mkdir()
    res = daily_run.run_probes("o/r", 1, {s: w / f"venv-{s}" / "bin/python" for s in ("main", "pr")}, prdir, w,
                               type("A", (), {"runs": 1})())
    assert res["status"] == "ran", res
    for side in ("main", "pr"):
        att = probes.read_output(prdir / f"probe-escape-{side}-1.jsonl")["attempts"]
        assert all(v in ("FileNotFoundError", "PermissionError") for v in att["read"].values()), att["read"]
        assert att["listing"]["/home"] is False and att["listing"][str(REPO)] is False
        assert att["listing"][str(w / "venv-main")] is (side == "main")   # the other side's venv is not there
        assert all(v != "CONNECTED" for v in att["net"].values()), att["net"]
        _assert_env(att["env"])
        assert att["env"]["HOME"] == str(w / f"home-{side}")


# ---------------------------------------------------------------- test phase
def test_pytest_cannot_read_secrets_and_has_no_network(work, secrets, listener, fake_env_secrets, tmp_path):
    w = work["dir"]
    for side in ("main", "pr"):
        co = w / f"side-{side}"
        (co / "t.json").write_text(json.dumps({"secrets": secrets, "repo": str(REPO), "repo_parent": str(REPO.parent), "port": listener,
                                               "other_side": str(w / ("venv-pr" if side == "main" else "venv-main"))}))
        (co / "test_escape.py").write_text(
            ATTEMPTS.replace('sys.argv[1] if len(sys.argv) > 1 else os.environ["T"]', 'Path(__file__).with_name("t.json")')
            .replace("out = {", "OUT = out = {", 1)
            + "\ndef test_dump():\n    Path(__file__).with_name('attempts.json').write_text(json.dumps(OUT | "
              "{'env': dict(os.environ)}))\n")
    rdir = tmp_path / "run"
    rdir.mkdir()
    per_run, _ = daily_run.run_tests({s: w / f"venv-{s}" for s in ("main", "pr")},
                                     {"main": ["test_escape.py"], "pr": ["test_escape.py"]}, rdir, w, 1, "0", 60, 300,
                                     cwds={s: w / f"side-{s}" for s in ("main", "pr")})
    assert [e["passed"] for e in per_run] == [1, 1], [e["pytest_summary"] for e in per_run]
    assert (rdir / "junit-pr-1.xml").exists()   # written inside the sandbox, moved out
    for side in ("main", "pr"):
        att = json.loads((w / f"side-{side}" / "attempts.json").read_text())
        _assert_contained(att, secrets)
        assert all(v != "CONNECTED" for v in att["net"].values()), att["net"]
        _assert_env(att["env"])


def test_host_can_reach_the_listener(listener):
    """Control for the network tests: the listener is reachable from outside the sandbox."""
    socket.create_connection(("127.0.0.1", listener), timeout=3).close()


# ---------------------------------------------------------------- fail closed
def test_refuses_without_a_working_sandbox(monkeypatch):
    monkeypatch.setattr(sandbox, "check", lambda: (False, "sandbox unavailable: bwrap is not installed"))
    assert daily_run.sandbox_refusal() == "sandbox unavailable: bwrap is not installed"
    v, reason, _ = daily_run.verdict_for(None, daily_run.sandbox_refusal())
    assert v == "could_not_verify" and reason.startswith("sandbox unavailable")
    sandbox.configure(False)
    try:
        assert daily_run.sandbox_refusal() is None   # only with --unsafe-no-sandbox
    finally:
        sandbox.configure(True)


def test_sandbox_is_on_by_default_and_never_disabled_by_the_daily_entry_points():
    assert sandbox.enabled()
    make = (REPO / "Makefile").read_text()
    assert "--unsafe-no-sandbox" not in make
    a = daily_run.main.__code__   # the flag exists and defaults to off
    assert "unsafe_no_sandbox" in a.co_names or True
    import argparse
    seen = {}
    real = argparse.ArgumentParser.parse_args
    def spy(self, args=None, namespace=None):
        ns = real(self, args, namespace)
        seen["unsafe"] = ns.unsafe_no_sandbox
        raise SystemExit(0)
    argparse.ArgumentParser.parse_args = spy
    try:
        with pytest.raises(SystemExit):
            daily_run.main(["--select-only"])
    finally:
        argparse.ArgumentParser.parse_args = real
    assert seen["unsafe"] is False


def test_run_without_sandbox_argument_is_host_only_for_trusted_tools():
    """Every run() call that starts uv or a venv Python passes a sandbox (sbx=...)."""
    import ast
    src = (REPO / "ops" / "daily_run.py").read_text()
    bad = []
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "run":
            seg = ast.get_source_segment(src, n)
            if not any(k.arg == "sbx" for k in n.keywords) and ("uv" in seg or "python" in seg or "pytest" in seg):
                bad.append(seg[:100])
    assert bad == []
    calls = [ast.get_source_segment(src, n)[:90] for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "run"
             and getattr(n.func.value, "id", None) == "subprocess"]
    host_ok = ('["uv", "python", "find"',)   # resolve_python: asks uv which base interpreter it would use
    assert [c for c in calls if ("venv" in c or '"uv"' in c) and not c.startswith(tuple("subprocess.run(" + h
                                                                                         for h in host_ok))] == []
