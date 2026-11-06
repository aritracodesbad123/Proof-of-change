"""An inherited runner config-file path must not enter the sandbox, and must not become a per-PR verdict.

PIP_CONFIG_FILE on the runner is a path. A product install replaces it with the empty-file sentinel so pip
reads no config. That sentinel is a remedied setting: the heavy-build check accepts it and the subprocess
does not see the path. A credential-like name is still UnsafeEnv, and that refusal is a run-level
infrastructure error, not could_not_verify on the pull request.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import guardrails.isolation as iso
from guardrails import sandbox
from ops import daily_run
from poc import pdf_always

HOST_PATH = "/opt/runner/SECRETPATH/pip.conf"
UV_PATH = "/opt/runner/SECRETPATH/uv.toml"
SECRET = "super-secret-key-value"


def _pdf_text(path: Path) -> str:
    data = path.read_bytes()
    assert data.startswith(b"%PDF")
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True).stdout
    return data.decode("latin-1", "replace")


def test_host_config_paths_are_dropped_and_auth_proxy_tls_stay():
    """The drop list is the config-file names only. A secret, a proxy and a certificate path stay in the dict."""
    src = {"PATH": "/bin", "HTTPS_PROXY": "http://proxy.example:3128", "SSL_CERT_FILE": "/etc/ssl/cert.pem",
           "NEBIUS_API_KEY": SECRET, "PIP_CONFIG_FILE": HOST_PATH, "UV_CONFIG_FILE": UV_PATH,
           "UV_NO_CONFIG": "1"}
    got = iso.without_host_config_paths(src)
    assert src["PIP_CONFIG_FILE"] == HOST_PATH   # the caller's dict, and the process environment, are not edited
    assert "PIP_CONFIG_FILE" not in got and "UV_CONFIG_FILE" not in got
    assert HOST_PATH not in repr(got) and UV_PATH not in repr(got)
    assert got["HTTPS_PROXY"] == "http://proxy.example:3128"
    assert got["SSL_CERT_FILE"] == "/etc/ssl/cert.pem"
    assert got["NEBIUS_API_KEY"] == SECRET and got["UV_NO_CONFIG"] == "1"
    # The sentinel is the remedied value and is kept. A credential-like name is still refused.
    sentinel = dict(got, PIP_CONFIG_FILE=os.devnull)
    assert iso.remedied_config_names(sentinel) == ["PIP_CONFIG_FILE"]
    with pytest.raises(iso.UnsafeEnv, match="credential-like"):
        iso.check_untrusted_env(sentinel)


def test_a_runner_path_is_not_remedied_and_its_value_is_not_in_the_error():
    with pytest.raises(iso.UnsafeEnv, match="not allowlisted") as ei:
        iso.check_untrusted_env({"PATH": "/bin", "PIP_CONFIG_FILE": HOST_PATH})
    text = str(ei.value)
    assert "PIP_CONFIG_FILE" in text and HOST_PATH not in text and "SECRETPATH" not in text


def test_sentinel_passes_the_heavy_build_check_and_a_secret_does_not():
    out = daily_run.with_compiler_jobs(
        {"PATH": "/bin", "SSL_CERT_FILE": "/etc/ssl/cert.pem", "PIP_CONFIG_FILE": os.devnull,
         "UV_CONFIG_FILE": UV_PATH}, jobs=1)
    assert out["PIP_CONFIG_FILE"] == os.devnull
    assert out["SSL_CERT_FILE"] == "/etc/ssl/cert.pem"
    assert "UV_CONFIG_FILE" not in out and UV_PATH not in repr(out)
    with pytest.raises(iso.UnsafeEnv, match="credential-like") as ei:
        daily_run.with_compiler_jobs(
            {"PATH": "/bin", "GH_TOKEN": SECRET, "PIP_CONFIG_FILE": HOST_PATH}, jobs=1)
    text = str(ei.value)
    assert "GH_TOKEN" in text and SECRET not in text and HOST_PATH not in text


def test_product_install_proceeds_without_the_inherited_path(tmp_path, monkeypatch):
    """The heavy-build check used to raise UnsafeEnv on PIP_CONFIG_FILE and stop the install."""
    monkeypatch.setenv("PIP_CONFIG_FILE", HOST_PATH)
    monkeypatch.setenv("UV_CONFIG_FILE", UV_PATH)
    monkeypatch.setenv("NEBIUS_API_KEY", SECRET)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:3128")
    monkeypatch.setenv("SSL_CERT_FILE", "/etc/ssl/cert.pem")
    monkeypatch.setenv("POC_HEAVY_BUILD_DIR", str(tmp_path / "slots"))
    monkeypatch.setenv("POC_BUILD_JOBS", "1")
    seen = []

    def fake_run(cmd, log, cwd=None, env=None, timeout=None, sbx=None):
        seen.append(dict(env or {}))
        return 0, 0.0

    monkeypatch.setattr(daily_run, "run", fake_run)
    co = tmp_path / "co"
    co.mkdir()
    ok, why = daily_run.install_side(tmp_path / "venv-pr", co, None, tmp_path / "log", "3.12", 30, None,
                                     isolated=True)
    assert ok, why
    assert seen
    blob = "\n".join(repr(e) for e in seen)
    assert HOST_PATH not in blob and UV_PATH not in blob and SECRET not in blob
    assert any(e.get("PIP_CONFIG_FILE") == os.devnull and e.get("UV_NO_CONFIG") == "1" for e in seen)
    assert all(e.get("SSL_CERT_FILE") == "/etc/ssl/cert.pem" for e in seen)
    assert os.environ["PIP_CONFIG_FILE"] == HOST_PATH
    assert os.environ["NEBIUS_API_KEY"] == SECRET
    assert os.environ["HTTPS_PROXY"] == "http://proxy.example:3128"


def test_sandbox_subprocess_env_does_not_contain_the_runner_path(tmp_path, monkeypatch):
    host = tmp_path / "pip.conf"
    host.write_text("[global]\nindex-url = https://user:leak-token@example.invalid/simple\n")
    monkeypatch.setenv("PIP_CONFIG_FILE", str(host))
    monkeypatch.setenv("NEBIUS_API_KEY", SECRET)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:3128")
    monkeypatch.setenv("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt")
    sandbox.configure(False)
    try:
        home = tmp_path / "home"
        env = daily_run.no_index_config_env(daily_run.base_env(home, install=True))
        log = tmp_path / "child.log"
        rc, _ = daily_run.run(
            ["/bin/sh", "-c", 'printf "PIP=%s\\n" "$PIP_CONFIG_FILE"; env | sort'],
            log, env=env, sbx=None)
        text = log.read_text()
        assert rc == 0, text
        assert str(host) not in text and "leak-token" not in text and SECRET not in text
        assert f"PIP={os.devnull}" in text
        assert "SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt" in text
        assert "HTTPS_PROXY" not in text   # not part of the allowlisted sandbox env
        # A caller that hands run() a dict still carrying the runner path: the subprocess does not receive it.
        # Proxy and TLS settings in that dict are not stripped.
        dirty_home = tmp_path / "h2"
        dirty_home.mkdir()
        dirty = {"PATH": os.environ["PATH"], "HOME": str(dirty_home), "PIP_CONFIG_FILE": str(host),
                 "SSL_CERT_FILE": "/etc/ssl/certs/ca-certificates.crt",
                 "HTTPS_PROXY": "http://proxy.example:3128"}
        log2 = tmp_path / "dirty.log"
        rc2, _ = daily_run.run(
            ["/bin/sh", "-c", 'printf "PIP=%s PROXY=%s TLS=%s\\n" "$PIP_CONFIG_FILE" "$HTTPS_PROXY" "$SSL_CERT_FILE"'],
            log2, env=dirty, sbx=None)
        got = log2.read_text()
        assert rc2 == 0, got
        assert str(host) not in got and "leak-token" not in got
        assert "PROXY=http://proxy.example:3128" in got
        assert "TLS=/etc/ssl/certs/ca-certificates.crt" in got
        wrapped, child, _cwd = sandbox.wrap(["/bin/true"], dirty, [dirty_home])
        assert str(host) not in repr(child) and child.get("HTTPS_PROXY") == "http://proxy.example:3128"
        assert wrapped[0] == "/bin/true"   # sandbox off: the command is unchanged, the env is still cleaned
        sandbox.configure(True)
        if sandbox.check()[0]:
            home_b = tmp_path / "home-bwrap"
            env_b = daily_run.no_index_config_env(daily_run.base_env(home_b, install=True))
            log_b = tmp_path / "bwrap.log"
            rc_b, _ = daily_run.run(
                ["/bin/sh", "-c", 'printf "PIP=%s\\n" "$PIP_CONFIG_FILE"'],
                log_b, env=env_b, sbx={"rw": [home_b], "ro": [], "network": False})
            text_b = log_b.read_text()
            assert rc_b == 0, text_b
            assert f"PIP={os.devnull}" in text_b
            assert str(host) not in text_b and "leak-token" not in text_b and SECRET not in text_b
    finally:
        sandbox.configure(True)
    assert os.environ["NEBIUS_API_KEY"] == SECRET
    assert os.environ["HTTPS_PROXY"] == "http://proxy.example:3128"


def _placeholder(tmp_path, pr=1515):
    a = SimpleNamespace(report_dir=str(tmp_path / "reports"), no_report=False)
    cfg = {"pkg": "loguru"}
    item = {"pr": pr, "title": "t"}
    rdir = tmp_path / "run"
    tag = f"loguru-{pr}"
    prdir = rdir / tag
    prdir.mkdir(parents=True)
    (prdir / "record.json").write_text(json.dumps(
        pdf_always.placeholder_record("Delgan/loguru", "loguru", pr, "t")))
    pdf_always.placeholder(a.report_dir, tag, f"Delgan/loguru#{pr}")
    return a, cfg, item, rdir, prdir, tag


def test_setup_retry_does_not_store_unsafe_env_as_an_install_result():
    """The setup helper catches install errors. An environment refusal is not one of them."""
    from poc import demo_helper

    def boom():
        raise iso.UnsafeEnv("refusing to run untrusted code with this environment: not allowlisted ['GH_TOKEN'], "
                            "credential-like names ['GH_TOKEN'], URLs with credentials in []")

    with pytest.raises(iso.UnsafeEnv, match="GH_TOKEN"):
        demo_helper.run_setup("main install", boom)
    failed = demo_helper.run_setup("main install", lambda: (False, "install failed (1)"))
    assert failed[0] is False and "install failed" in failed[1]


def test_genuine_unsafe_env_is_run_level_and_not_a_per_pr_verdict(tmp_path, monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", SECRET)
    monkeypatch.setenv("PIP_CONFIG_FILE", HOST_PATH)
    a, cfg, item, rdir, prdir, tag = _placeholder(tmp_path)
    err = iso.UnsafeEnv(
        "refusing to run untrusted code with this environment: not allowlisted ['GH_TOKEN'], "
        f"credential-like names ['GH_TOKEN'], URLs with credentials in [] {SECRET} {HOST_PATH}")
    raised = daily_run.abandon_pr_for_unsafe_env(rdir, a, cfg, item, err)
    assert isinstance(raised, daily_run.EnvInfrastructure)
    text = str(raised)
    assert text.startswith("infrastructure failure:")
    assert "not a result about a pull request" in text
    assert "could_not_verify" not in text
    assert "GH_TOKEN" in text
    assert SECRET not in text and HOST_PATH not in text and "SECRETPATH" not in text
    assert not (prdir / "record.json").exists()
    assert not (Path(a.report_dir) / tag / "REPORT.pdf").exists()
    # A finished record is not rewritten, and another exception is still a per-PR could_not_verify.
    (prdir).mkdir(parents=True, exist_ok=True)
    (prdir / "record.json").write_text(json.dumps({"record_kind": "pr_run", "verdict": "verified", "reason": "ok"}))
    again = daily_run.abandon_pr_for_unsafe_env(rdir, a, cfg, item, iso.UnsafeEnv("not allowlisted ['GH_TOKEN']"))
    assert "infrastructure failure" in str(again)
    assert json.loads((prdir / "record.json").read_text())["verdict"] == "verified"
    other = daily_run.harness_error_record("Delgan/loguru", cfg, {"pr": 9, "title": "t"}, rdir, a, {},
                                           ValueError("boom"))
    assert other["verdict"] == "could_not_verify" and "UnsafeEnv" not in other["reason"]


def test_env_infrastructure_writes_a_run_level_nogo_pdf(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    monkeypatch.setenv("POC_REPORT_DIR", str(reports))
    monkeypatch.setenv("NEBIUS_API_KEY", SECRET)
    monkeypatch.setenv("PIP_CONFIG_FILE", HOST_PATH)

    def boom(argv=None):
        raise daily_run.EnvInfrastructure(daily_run.infrastructure_env_reason(iso.UnsafeEnv(
            "not allowlisted ['GH_TOKEN'], credential-like names ['GH_TOKEN'] "
            f"{SECRET} {HOST_PATH}")))

    monkeypatch.setattr(daily_run, "_main", boom)
    assert daily_run.main([]) == 1
    found = list(reports.rglob("SUMMARY.pdf"))
    assert len(found) == 1, found
    text = _pdf_text(found[0])
    assert "NO-GO" in text and "could not run" in text
    assert "infrastructure failure" in text
    assert "not a result about a pull request" in text
    assert "could_not_verify" not in text
    assert SECRET not in text and "SECRETPATH" not in text
