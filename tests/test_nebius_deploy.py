"""The Nebius VM files in deploy/nebius/ name only settings the code reads, commit no values, and keep the
console and the GitHub App listener on 127.0.0.1 behind Caddy."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy" / "nebius"
SETUP_ONLY = {"POC_SSH_ALLOW_CIDRS"}  # read by setup.sh only
# Non-secret switches the template may preset; everything else must be empty.
PRESET = {"POC_HOSTED": "1", "POC_REQUIRE_CONTREE": "1", "POC_DAILY_CAP": "5", "POC_COOKIE_SECURE": "1"}


def _template() -> dict[str, str]:
    out = {}
    for line in (DEPLOY / "env.template").read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            k, _, v = line.partition("=")
            out[k.strip()] = v
    return out


def _code_text() -> str:
    return "\n".join(p.read_text(errors="ignore") for d in ("poc", "ops", "reports")
                     for p in (ROOT / d).rglob("*.py"))


def test_template_names_are_read_by_the_code():
    code = _code_text()
    missing = [k for k in _template() if k not in SETUP_ONLY and not re.search(rf"\b{k}\b", code)]
    assert missing == []


def test_template_commits_no_values():
    for k, v in _template().items():
        assert v == PRESET.get(k, ""), k


def test_template_turns_on_hosted_contree_and_both_caps():
    t = _template()
    for k in ("POC_HOSTED", "POC_REQUIRE_CONTREE", "POC_DAILY_CAP", "POC_TAVILY_CREDIT_CAP",
              "NEBIUS_API_KEY", "NEBIUS_PROJECT_ID", "TAVILY_API_KEY", "GITHUB_WEBHOOK_SECRET"):
        assert k in t


def test_services_bind_localhost_only():
    console = (DEPLOY / "proof-of-change-console.service").read_text()
    app = (DEPLOY / "proof-of-change-app.service").read_text()
    assert "-m poc.console_api --host 127.0.0.1 --port 8787" in console
    assert "-m poc.github_app --host 127.0.0.1 --port 8080" in app
    assert console.count("ExecStart=") == 1
    for unit in (console, app):
        assert "EnvironmentFile=/etc/proof-of-change/env" in unit
        assert "0.0.0.0" not in unit


def test_caddy_routes_webhook_and_console():
    caddy = (DEPLOY / "Caddyfile.template").read_text()
    assert "path /webhook" in caddy and "reverse_proxy 127.0.0.1:8080" in caddy
    assert "reverse_proxy 127.0.0.1:8787" in caddy


def test_ssh_is_key_only_and_checked_before_reload():
    conf = (DEPLOY / "sshd-hardening.conf").read_text()
    for line in ("PasswordAuthentication no", "PermitRootLogin no", "KbdInteractiveAuthentication no"):
        assert line in conf
    setup = (DEPLOY / "setup.sh").read_text()
    assert setup.index("sshd -t") < setup.index("systemctl reload ssh")
    assert "chmod 600" in setup and "POC_SSH_ALLOW_CIDRS" in setup
    for port in ("80/tcp", "443/tcp"):
        assert f"ufw allow {port}" in setup


def test_health_paths_exist_in_the_code():
    assert '"/api/health"' in (ROOT / "poc" / "console_api.py").read_text()
    gh = (ROOT / "poc" / "github_app.py").read_text()
    assert '"/health"' in gh and '"/webhook"' in gh


def test_app_code_is_read_only_to_the_services():
    for name in ("proof-of-change-console.service", "proof-of-change-app.service"):
        unit = (DEPLOY / name).read_text()
        rw = [ln for ln in unit.splitlines() if ln.startswith("ReadWritePaths=")]
        assert rw == ["ReadWritePaths=/var/lib/proof-of-change"], name
        assert "ProtectSystem=strict" in unit
    setup = (DEPLOY / "setup.sh").read_text()
    assert 'chown -R root:root "$APP"' in setup
    assert "proof-of-change:proof-of-change \"$APP\"" not in setup


def test_signup_needs_an_invite_code_generated_at_setup():
    t = _template()
    assert t["POC_INVITE_CODE"] == "" and t["POC_SIGNUP_DISABLED"] == ""
    auth = (ROOT / "poc" / "console_auth.py").read_text()
    assert '"POC_INVITE_CODE"' in auth and '"POC_SIGNUP_DISABLED"' in auth
    assert "set_if_empty POC_INVITE_CODE" in (DEPLOY / "setup.sh").read_text()


def test_node_download_is_checked_before_extracting():
    setup = (DEPLOY / "setup.sh").read_text()
    assert "SHASUMS256.txt" in setup
    assert setup.index("sha256sum -c") < setup.index("tar -xJf")
    assert "| tar" not in setup  # never stream an unchecked download into tar
