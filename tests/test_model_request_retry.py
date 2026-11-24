"""Transient claims and probe requests are retried. A 4xx is not. AI unavailable does not lower a verdict."""
import io
import json
import logging

import pytest

from ops import daily_run as dr
from poc import model_provider


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http(code):
    def boom(req, timeout=None):
        raise model_provider.urllib.error.HTTPError(req.full_url, code, "no", {}, io.BytesIO(b""))
    return boom


def _ok(payload):
    body = json.dumps({"choices": [{"message": {"content": json.dumps(payload)}}]}).encode()
    return lambda req, timeout=None: _Resp(body)


@pytest.fixture
def no_wait(monkeypatch):
    monkeypatch.setattr(model_provider, "TRANSIENT_BACKOFF_S", (0, 0))


def test_a_transient_http_error_is_retried_twice_then_says_ai_unavailable(monkeypatch, no_wait, caplog):
    calls = {"n": 0}

    def boom(req, timeout=None):
        calls["n"] += 1
        raise model_provider.urllib.error.HTTPError(req.full_url, 503, "unavailable", {}, io.BytesIO(b""))

    monkeypatch.setattr(model_provider.urllib.request, "urlopen", boom)
    with caplog.at_level(logging.WARNING, logger="poc.model_provider"):
        with pytest.raises(model_provider.ProviderError) as caught:
            model_provider.NebiusProvider("k").complete_json("claims", "s", "u", {}, {})
    assert calls["n"] == 3
    assert "HTTPError 503" in str(caught.value) and "AI unavailable" in str(caught.value)
    assert caplog.text.count("HTTP 503") == 3


def test_a_transient_failure_succeeds_on_a_later_attempt(monkeypatch, no_wait):
    calls = {"n": 0}

    def flaky(req, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("timed out")
        return _ok({"claims": []})(req, timeout)

    monkeypatch.setattr(model_provider.urllib.request, "urlopen", flaky)
    assert model_provider.NebiusProvider("k").complete_json("probes", "s", "u", {}, {}) == {"claims": []}
    assert calls["n"] == 3


@pytest.mark.parametrize("exc", [
    lambda: TimeoutError("timed out"),
    lambda: ConnectionResetError("reset"),
    lambda: json.JSONDecodeError("Expecting value", "", 0),
])
def test_timeouts_resets_and_truncated_json_are_retried(monkeypatch, no_wait, exc):
    calls = {"n": 0}
    error = exc()

    def boom(req, timeout=None):
        calls["n"] += 1
        if isinstance(error, json.JSONDecodeError):
            return _Resp(b"{")
        raise error

    monkeypatch.setattr(model_provider.urllib.request, "urlopen", boom)
    with pytest.raises(model_provider.ProviderError) as caught:
        model_provider.NebiusProvider("k").complete_json("claims", "s", "u", {}, {})
    assert calls["n"] == 3
    assert "AI unavailable" in str(caught.value)
    assert type(error).__name__ in str(caught.value)


def test_a_client_error_is_not_retried_and_is_not_ai_unavailable(monkeypatch, no_wait, caplog):
    calls = {"n": 0}

    def boom(req, timeout=None):
        calls["n"] += 1
        raise model_provider.urllib.error.HTTPError(req.full_url, 400, "bad", {}, io.BytesIO(b""))

    monkeypatch.setattr(model_provider.urllib.request, "urlopen", boom)
    with caplog.at_level(logging.WARNING, logger="poc.model_provider"):
        with pytest.raises(model_provider.ProviderError) as caught:
            model_provider.NebiusProvider("k").complete_json("probes", "s", "u", {}, {})
    assert calls["n"] == 1
    assert "HTTPError 400" in str(caught.value)
    assert "AI unavailable" not in str(caught.value)
    assert caplog.text.count("HTTP 400") == 1


def test_an_auth_refusal_is_not_retried(monkeypatch, no_wait):
    calls = {"n": 0}

    def boom(req, timeout=None):
        calls["n"] += 1
        raise model_provider.urllib.error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(b""))

    monkeypatch.setattr(model_provider.urllib.request, "urlopen", boom)
    with pytest.raises(model_provider.ProviderRejected):
        model_provider.NebiusProvider("k").complete_json("claims", "s", "u", {}, {})
    assert calls["n"] == 1


def test_a_judge_request_is_not_retried(monkeypatch, no_wait):
    calls = {"n": 0}
    monkeypatch.setattr(model_provider.urllib.request, "urlopen", _http(503))

    def boom(req, timeout=None):
        calls["n"] += 1
        raise model_provider.urllib.error.HTTPError(req.full_url, 503, "unavailable", {}, io.BytesIO(b""))

    monkeypatch.setattr(model_provider.urllib.request, "urlopen", boom)
    with pytest.raises(model_provider.ProviderError) as caught:
        model_provider.NebiusProvider("k").complete_json("judge", "s", "u", {}, {})
    assert calls["n"] == 1
    assert "AI unavailable" not in str(caught.value)


def _clean(errors, items=None, verdict="verified", reason="4 tests fixed"):
    return {
        "verdict": verdict, "reason": reason, "baseline": "full",
        "probes": {"items": items or []},
        "probe_plan": {"errors": errors},
    }


def test_ai_unavailable_does_not_demote_a_verified_result():
    gated = dr.ai_probe_gate(_clean(["nebius claims request failed: HTTPError"]))
    assert gated["verdict"] == "could_not_verify"
    out = dr.hold_when_ai_unavailable(gated)
    assert out["verdict"] == "verified"
    assert "AI unavailable" in out["reason"]
    assert "no AI-written probe" not in out["reason"]


def test_a_client_error_still_leaves_the_ai_probe_gate_in_place():
    gated = dr.ai_probe_gate(_clean(["nebius claims request failed: HTTPError 400"]))
    out = dr.hold_when_ai_unavailable(gated)
    assert out["verdict"] == "could_not_verify"
    assert "no AI-written probe" in out["reason"]


def test_a_rejected_probe_is_still_not_verified():
    errors = ["nebius probes request failed: TimeoutError", "probe 'p1' rejected: code does not parse: unmatched '}'"]
    gated = dr.ai_probe_gate(_clean(errors))
    out = dr.hold_when_ai_unavailable(gated)
    assert out["verdict"] == "could_not_verify"
    assert "AI unavailable" not in out["reason"]


def test_a_model_probe_that_missed_the_change_is_still_not_verified():
    item = {"id": "model-1", "source": "model", "probe_changed_line_coverage": {"changed_lines_covered": 0}}
    gated = dr.ai_probe_gate(_clean(["nebius claims request failed: TimeoutError"], items=[item]))
    out = dr.hold_when_ai_unavailable(gated)
    assert out["verdict"] == "could_not_verify"


def test_ai_unavailable_does_not_hide_needs_attention():
    rec = _clean(["nebius probes request failed: TimeoutError"], verdict="needs_attention", reason="1 regression")
    out = dr.hold_when_ai_unavailable(rec)
    assert out["verdict"] == "needs_attention"
    assert "AI unavailable" in out["reason"]
