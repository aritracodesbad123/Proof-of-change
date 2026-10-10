"""Untrusted code (installs and builds, pytest, probes, the release-pair runner) gets an ALLOWLISTED environment only
(guardrails/isolation.py). These tests set fake credentials, start real subprocesses through the same code paths the
daily run uses, and check what the child process actually sees."""
import json
import sys
from pathlib import Path

import pytest

import guardrails.isolation as iso
from guardrails import sandbox
from ops import daily_run
from poc import probes

FAKE_SECRETS = {"NEBIUS_KEY": "fake-nebius", "TAVILY_KEY": "fake-tavily", "OPENAI_APIKEY": "fake-openai",
                "GH_PAT": "fake-pat", "DATABASE_URL": "postgres://u:fake-pw@db/x", "NPM_AUTH": "fake-npm",
                "GITHUB_POC_TOKEN": "fake-poc", "GITHUB_TOKEN": "fake-gh", "AWS_SECRET_ACCESS_KEY": "fake-aws"}
NOISE = {"PYTHONPATH": "/somewhere", "PIP_INDEX_URL": "https://example.invalid/simple", "UV_INDEX_URL": "https://x",
         "CI": "true", "SSH_AUTH_SOCK": "/tmp/agent", "DISPLAY": ":0", "LD_PRELOAD": "/tmp/x.so",
         "PYTHONSTARTUP": "/tmp/s.py", "VIRTUAL_ENV": "/elsewhere", "XDG_CONFIG_HOME": "/real/.config",
         "HTTPS_PROXY": "http://user:pw@proxy:3128"}
RUN_KEYS = {"PATH", "HOME", "LANG", "LC_ALL", "PYTHONHASHSEED", "PYTHONDONTWRITEBYTECODE", "MPLBACKEND",
            "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"}
INSTALL_KEYS = RUN_KEYS | {"UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR", "UV_LINK_MODE", "UV_NO_CONFIG"}


@pytest.fixture
def no_sandbox():
    """The allowlist alone (these run anywhere, also where bubblewrap cannot start); test_sandbox.py repeats the
    subprocess checks inside the real sandbox."""
    sandbox.configure(False)
    yield
    sandbox.configure(True)


@pytest.fixture
def hostile_env(monkeypatch):
    """A parent environment full of credentials and settings that must not reach untrusted code."""
    for k in ("TERM", "TMPDIR", "SOURCE_DATE_EPOCH", "SSL_CERT_FILE", "UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR",
              "XDG_CACHE_HOME", "XDG_DATA_HOME"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("HOME", "/real/home")
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LC_ALL", "C.UTF-8")   # set, so the child Python never adds LC_CTYPE (PEP 538)
    for k, v in (FAKE_SECRETS | NOISE).items():
        monkeypatch.setenv(k, v)


def _no_secret_visible(env: dict):
    leaked = sorted(k for k in FAKE_SECRETS if k in env) + sorted(k for k, v in env.items()
                                                                  if any(s in v for s in FAKE_SECRETS.values()))
    assert leaked == []
    assert not any(iso.SECRET_NAME.search(k) for k in env)


# ---------------------------------------------------------------- the env itself
def test_run_env_is_exactly_the_allowlist(hostile_env, tmp_path):
    env = daily_run.base_env(tmp_path / "home-pr")
    assert set(env) == RUN_KEYS and set(env) <= iso.RUN_ALLOWLIST
    assert env == {"PATH": __import__("os").environ["PATH"], "HOME": str(tmp_path / "home-pr"), "LANG": "C.UTF-8",
                   "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "MPLBACKEND": "Agg",
                   **{k: "1" for k in daily_run.THREAD_ENV}}
    assert (tmp_path / "home-pr").is_dir() and env["HOME"] != "/real/home"
    _no_secret_visible(env)


def test_install_env_adds_only_uv_settings(hostile_env, tmp_path):
    env = daily_run.base_env(tmp_path / "h", install=True)
    assert set(env) == INSTALL_KEYS
    assert env["UV_CACHE_DIR"] == "/real/home/.cache/uv"                # the real cache, not the temp home's
    assert env["UV_PYTHON_INSTALL_DIR"] == "/real/home/.local/share/uv/python"
    assert env["UV_LINK_MODE"] == "copy" and env["UV_NO_CONFIG"] == "1"
    _no_secret_visible(env)
    scm = daily_run.base_env(tmp_path / "h", install=True, SETUPTOOLS_SCM_PRETEND_VERSION="9999.0.0")
    assert set(scm) - set(env) == {"SETUPTOOLS_SCM_PRETEND_VERSION"}


def test_optional_pass_through_values_only_when_set(hostile_env, monkeypatch, tmp_path):
    for k, v in {"TERM": "xterm", "TMPDIR": "/tmp/t", "SOURCE_DATE_EPOCH": "0", "SSL_CERT_FILE": "/etc/ca.pem"}.items():
        monkeypatch.setenv(k, v)
    assert set(daily_run.base_env(tmp_path)) == RUN_KEYS | {"TERM", "TMPDIR", "SOURCE_DATE_EPOCH", "SSL_CERT_FILE"}


def test_extras_and_unsafe_envs_fail_loudly(tmp_path):
    with pytest.raises(iso.UnsafeEnv):
        daily_run.base_env(tmp_path, GH_PAT="x")                       # not an allowed extra
    with pytest.raises(iso.UnsafeEnv):
        daily_run.base_env(tmp_path, SETUPTOOLS_SCM_PRETEND_VERSION="1")   # extras are install-only
    with pytest.raises(iso.UnsafeEnv, match="not allowlisted"):
        iso.check_untrusted_env({"PATH": "/bin", "FOO": "1"})
    with pytest.raises(iso.UnsafeEnv, match="URLs with credentials"):
        iso.check_untrusted_env({"PATH": "/bin", "SSL_CERT_FILE": "https://u:pw@host/x"})
    with pytest.raises(ValueError):
        daily_run.run(["true"], tmp_path / "log")                      # run() never falls back to os.environ


@pytest.mark.parametrize("name", list(FAKE_SECRETS) + ["MY_SESSION_ID", "SENTRY_DSN", "SIGNING_KEY", "KEY", "PAT"])
def test_denylist_backstop_rejects_secret_names_in_the_allowlist(name):
    with pytest.raises(iso.UnsafeEnv, match="look like credentials"):
        iso.check_allowlist(iso.INSTALL_ALLOWLIST | {name})
    with pytest.raises(iso.UnsafeEnv, match="credential-like"):
        iso.check_untrusted_env({"PATH": "/bin", name: "x"}, iso.INSTALL_ALLOWLIST | {name})


def test_allowlist_has_no_secret_like_names():
    iso.check_allowlist(iso.INSTALL_ALLOWLIST)
    assert not any(iso.SECRET_NAME.search(k) for k in iso.INSTALL_ALLOWLIST)
    assert "PATH" in iso.RUN_ALLOWLIST and not iso.SECRET_NAME.search("PATH")


# ---------------------------------------------------------------- real subprocesses
def _fake_venv(root: Path, side: str) -> Path:
    """<root>/venv-<side>/bin/python: execs this test interpreter, leaving the environment untouched."""
    py = root / f"venv-{side}" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text(f"#!{sys.executable}\nimport os, sys\nos.execv(sys.executable, [sys.executable, *sys.argv[1:]])\n")
    py.chmod(0o755)
    return py


DUMP_PROBE = ('import json, os\nPROBE = {"id": "env-dump", "target": "o/r#1", "about": "environment", "claims": []}\n'
              'print(json.dumps({"observations": {"env": dict(os.environ)}}))\n')


def test_probe_subprocess_sees_only_the_allowlist(hostile_env, no_sandbox, tmp_path, monkeypatch):
    work, prdir = tmp_path / "work", tmp_path / "run"
    prdir.mkdir()
    pythons = {s: _fake_venv(work, s) for s in ("main", "pr")}
    probe = tmp_path / "1.py"
    probe.write_text(DUMP_PROBE)
    monkeypatch.setattr(probes, "find_probes", lambda repo, pr: [probe])
    monkeypatch.setattr(daily_run, "repo_relative", lambda p: str(p))
    res = daily_run.run_probes("o/r", 1, pythons, prdir, work, type("A", (), {"runs": 1})())
    assert res["status"] == "ran" and res["items"][0]["per_run"][0]["ok"]
    for side in ("main", "pr"):
        seen = probes.read_output(prdir / f"probe-env-dump-{side}-1.jsonl")["env"]
        _no_secret_visible(seen)
        assert not set(NOISE) & set(seen)
        assert set(seen) == RUN_KEYS                                     # exactly the allowlist
        assert seen == daily_run.base_env(work / f"home-{side}")
        assert seen["HOME"] == str(work / f"home-{side}")                # per-side temporary home


def test_pytest_subprocess_sees_only_the_allowlist(hostile_env, no_sandbox, tmp_path):
    work, rdir = tmp_path / "work", tmp_path / "run"
    rdir.mkdir()
    venvs = {s: _fake_venv(work, s).parent.parent for s in ("main", "pr")}
    cwds = {}
    for s in ("main", "pr"):
        cwds[s] = tmp_path / f"side-{s}"
        cwds[s].mkdir()
        (cwds[s] / "test_env.py").write_text(
            "import json, os\n\ndef test_dump():\n"
            "    with open(os.path.join(os.getcwd(), 'env.json'), 'w') as f:\n        json.dump(dict(os.environ), f)\n")
    per_run, results = daily_run.run_tests(venvs, {"main": ["test_env.py"], "pr": ["test_env.py"]}, rdir, work, 1,
                                           "0", 60, 120, cwds=cwds)
    assert [e["passed"] for e in per_run] == [1, 1], [e["pytest_summary"] for e in per_run]
    for s in ("main", "pr"):
        seen = json.loads((cwds[s] / "env.json").read_text())
        _no_secret_visible(seen)
        added_by_pytest = {"PYTEST_CURRENT_TEST", "PYTEST_VERSION"}
        assert set(seen) - added_by_pytest == RUN_KEYS                   # exactly the allowlist
        assert seen["HOME"] == str(work / f"home-{s}")


def test_install_subprocess_sees_only_the_allowlist(hostile_env, tmp_path, monkeypatch):
    """install_side's commands (uv venv / uv pip install of the PR checkout) run with the install allowlist."""
    calls = []

    def fake_run(cmd, log, cwd=None, env=None, timeout=None, sbx=None):
        calls.append(env)
        return 0, 0.0
    monkeypatch.setattr(daily_run, "run", fake_run)
    ok, _ = daily_run.install_side(tmp_path / "venv-pr", tmp_path, None, tmp_path / "log", "3.12", 60, None)
    assert ok and calls
    for env in calls:
        _no_secret_visible(env)
        assert set(env) - {"SETUPTOOLS_SCM_PRETEND_VERSION"} == INSTALL_KEYS and env["HOME"] == str(tmp_path / "home-pr")


def test_release_pair_runner_gets_the_allowlist(hostile_env, tmp_path, monkeypatch):
    import harness.run as hr
    got = {}
    monkeypatch.setattr(hr, "find_runner", lambda: tmp_path / "br_run.py")
    monkeypatch.setattr(hr.subprocess, "call", lambda cmd, env: got.setdefault("env", env) and 1)
    hr.main(["--data-root", str(tmp_path / "data")])
    _no_secret_visible(got["env"])
    assert set(got["env"]) == INSTALL_KEYS and got["env"]["HOME"] == str(tmp_path / "data" / "home")
