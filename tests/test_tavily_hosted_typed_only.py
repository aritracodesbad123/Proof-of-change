"""On a hosted console a user check uses only the typed Tavily key; a Codespace keeps its secret."""
from poc import console_api, related_reports, session_key

SERVER = "server-tavily-key-000"
TYPED = "typed-tavily-key-111"


def _env(**extra):
    base = {"PATH": "/usr/bin", "TAVILY_API_KEY": SERVER}
    base.update(extra)
    return base


def test_hosted_without_typed_key_gets_no_tavily_key_and_skips_lookup(capsys):
    session_key.clear_key("hosted-a")
    env, secrets = console_api.child_environment(_env(), "recorded", "hosted-a")
    assert "TAVILY_API_KEY" not in env
    assert SERVER in secrets
    called = []
    out = related_reports.collect({"title": "x", "repo": "a/b"}, env=env, fetch=lambda q: called.append(q))
    assert out["status"] == "skipped" and not called
    assert related_reports.SKIP_LOG in capsys.readouterr().out


def test_hosted_with_typed_key_uses_the_typed_key():
    session_key.set_tavily_key("hosted-b", TYPED)
    try:
        env, secrets = console_api.child_environment(_env(), "recorded", "hosted-b")
        assert env["TAVILY_API_KEY"] == TYPED
        assert SERVER in secrets and TYPED in secrets
    finally:
        session_key.clear_key("hosted-b")


def test_codespace_keeps_the_secret_fallback():
    session_key.clear_key("cs-c")
    for flag in ("CODESPACES", "POC_SINGLE_USER"):
        env, secrets = console_api.child_environment(_env(**{flag: "true"}), "recorded", "cs-c")
        assert env["TAVILY_API_KEY"] == SERVER
        assert SERVER in secrets
