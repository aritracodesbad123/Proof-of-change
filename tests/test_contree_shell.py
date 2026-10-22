"""Contree runs commands with /bin/sh (dash on Debian images): setup scripts must still work there."""
import shutil
import subprocess
import types

import pytest

from ops import daily_run
from poc import contree_sandboxes as cs

SH = shutil.which("dash") or shutil.which("sh")


def _run_sh(script: str, path_env: str | None = None):
    env = {"PATH": path_env} if path_env is not None else None
    return subprocess.run([SH, "-c", script], capture_output=True, text=True, env=env, timeout=30)


def _checkpoint_script() -> str:
    seen = {}

    def runner(shell, disposable, image_ref, timeout, files):
        seen["shell"] = shell
        return {"exit_code": 0, "stdout": "", "stderr": "", "uuid": "u1"}

    cs.ContreeSession(runner=runner).checkpoint_main("echo installed", timeout=5)
    return seen["shell"]


@pytest.mark.skipif(SH is None or shutil.which("bash") is None, reason="needs sh and bash")
def test_generated_setup_script_runs_under_plain_sh_with_bash():
    script = cs.bash_wrapped(_checkpoint_script().replace("mkdir -p /work\ncd /work\n", ""))
    r = _run_sh(script)
    assert r.returncode == 0, r.stderr
    assert "installed" in r.stdout


@pytest.mark.skipif(SH is None or shutil.which("bash") is None, reason="needs sh and bash")
def test_pipefail_is_active_under_bash():
    r = _run_sh(cs.bash_wrapped("set -euo pipefail\nfalse | true\necho unreachable"))
    assert r.returncode != 0 and "unreachable" not in r.stdout


@pytest.mark.skipif(SH is None, reason="needs sh")
def test_falls_back_to_set_eu_without_bash(tmp_path):
    # PATH with only the basic tools, no bash
    for tool in ("echo", "false", "true"):
        p = shutil.which(tool)
        if p:
            (tmp_path / tool).symlink_to(p)
    script = cs.bash_wrapped("set -euo pipefail\necho fallback-ok\nfalse\necho unreachable")
    r = _run_sh(script, path_env=str(tmp_path))
    assert "fallback-ok" in r.stdout and "unreachable" not in r.stdout
    assert "pipefail" not in r.stderr and r.returncode != 0


def test_real_client_receives_wrapped_shell(monkeypatch):
    got = {}

    class Img:
        def run(self, shell, **kw):
            got["shell"] = shell
            return types.SimpleNamespace(wait=lambda: types.SimpleNamespace(exit_code=0, stdout="", stderr="", uuid="x"))

    client = types.SimpleNamespace(images=types.SimpleNamespace(oci=lambda ref: Img(), use=lambda *a, **k: Img()))
    sess = cs.ContreeSession()
    sess._client = client
    sess.run_op("base", "set -euo pipefail\necho hi", disposable=True, timeout=5)
    assert got["shell"].startswith("if command -v bash")
    assert "set -eu\necho hi" in got["shell"]


def test_setup_failure_reason_has_exit_code_and_redacted_tail(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "sekret-key-123")
    monkeypatch.setenv("NEBIUS_PROJECT_ID", "proj-456")

    def runner(shell, disposable, image_ref, timeout, files):
        return {"exit_code": 1, "stdout": "", "uuid": None,
                "stderr": "noise\nERROR: No matching distribution found for foo (token sekret-key-123 proj-456)"}

    with pytest.raises(cs.ContreeError) as ei:
        cs.prepare_source_pair("o/r", "a" * 40, "b" * 40, runner=runner)
    e = ei.value
    assert e.exit_code == 1 and not e.auth
    assert "exit 1" in str(e) and "No matching distribution" in str(e)
    for secret in ("sekret-key-123", "proj-456"):
        assert secret not in str(e) and secret not in e.stderr_tail
    refusal, entry = daily_run.contree_refusal(e)
    assert "Nebius key" not in refusal and "exit 1" in refusal
    assert entry["exit_code"] == 1 and "No matching distribution" in entry["stderr_tail"]
    assert entry["auth_error"] is False


def test_auth_error_blames_credentials_only_then():
    class ForbiddenError(Exception):
        pass

    class Img:
        def run(self, **kw):
            raise ForbiddenError("nope")

    sess = cs.ContreeSession()
    sess._client = types.SimpleNamespace(images=types.SimpleNamespace(oci=lambda ref: Img()))
    with pytest.raises(cs.ContreeError) as ei:
        sess.run_op("base", "echo", disposable=True, timeout=5)
    assert ei.value.auth
    refusal, entry = daily_run.contree_refusal(ei.value)
    assert "Check your Nebius key" in refusal and entry["auth_error"] is True


def test_record_keeps_error_output(monkeypatch):
    def boom(*a, **k):
        raise cs.ContreeError("main checkpoint install failed (exit 2)", exit_code=2, stderr_tail="sh: bad")
    monkeypatch.setattr(cs, "prepare_source_pair", boom)
    a = types.SimpleNamespace(sandbox_backend="contree")
    monkeypatch.setattr(daily_run, "product_route", lambda a: False)
    rec = {}
    refusal = daily_run._maybe_prepare_contree(a, "o/r", "a", "b", rec, 5)
    assert refusal and rec["contree"]["stderr_tail"] == "sh: bad" and rec["contree"]["exit_code"] == 2


def test_stderr_tail_hides_github_token_sk_token_and_url_password(monkeypatch):
    ghp = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    sk = "sk-" + "fakeKey1234567890abcdef"
    pw = "hunter2Secret"
    tok = "plain" + "TokenValue987"
    stderr = (f"fatal: auth with {ghp} failed\n"
              f"auth with {sk} rejected\n"
              f"pip: index token={tok} rejected\n"
              f"Looking in https://deploy:{pw}@pypi.example.com/simple\n")

    def runner(shell, disposable, image_ref, timeout, files):
        return {"exit_code": 1, "stdout": "", "stderr": stderr, "uuid": "u1"}

    with pytest.raises(cs.ContreeError) as ei:
        cs.ContreeSession(runner=runner).checkpoint_main("echo installed", timeout=5)
    _, entry = daily_run.contree_refusal(ei.value)
    rec = {"contree": entry}
    for leaked in (ghp, sk, pw, tok):
        assert leaked not in rec["contree"]["stderr_tail"]
        assert leaked not in rec["contree"]["failed"]
    assert "https://deploy:***@pypi.example.com" in rec["contree"]["stderr_tail"]


def test_redact_hides_basic_auth_header():
    import base64
    cred = base64.b64encode(("deploy" + ":" + "s3cr" + "etPw").encode()).decode()
    for hdr in (f"Authorization: Basic {cred}", f"authorization: basic {cred}"):
        out = cs.redact(f"curl: {hdr}\n", env={})
        assert cred not in out and "<redacted>" in out


def test_redact_hides_plain_password_values():
    a, b, c = ("pa" + "ssVal42", "pw" + "dVal43", "pd" + "Val44")
    text = f"url?password={a}&x=1 PASSWD={b} cfg Pwd='{c}'"
    out = cs.redact(text, env={})
    for v in (a, b, c):
        assert v not in out
    assert "&x=1" in out and "PASSWD=<redacted>" in out


def test_redact_leaves_ordinary_basic_text_alone():
    text = "Running basic tests\nbasic setup ok"
    assert cs.redact(text, env={}) == text


def test_redact_token_keeps_following_query_params():
    val = "abc" + "Tok123"
    out = cs.redact(f"GET /api?token={val}&page=2", env={})
    assert val not in out and "&page=2" in out
