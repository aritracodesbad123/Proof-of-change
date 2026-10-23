"""Product checks retry a transient Contree API timeout or 5xx, at most 3 tries, and never run locally."""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from poc import contree_sandboxes as cs

_REAL_SDK_VERSION = cs._sdk_version


class ApiTimeoutError(Exception):
    pass


class ServerError(Exception):
    status_code = 503


class Forbidden(Exception):
    pass


class ContreeTransportError(Exception):
    pass


class _Client:
    """Fake ContreeSync. run().wait() first creates the run via _start_operation (as the SDK does), then waits.

    Each outcome is a result, an exception raised before the run is created (start failure), or ("wait", exc):
    the run is created and the wait then fails."""

    def __init__(self, outcomes, seen):
        self.outcomes, self.seen, self.created = outcomes, seen, []
        img = SimpleNamespace(run=self._run)
        self.images = SimpleNamespace(oci=lambda ref: img, use=lambda ref, strict=True: img)

    async def _start_operation(self, request):
        self.created.append(request.command)
        return f"op-{len(self.created)}"

    def _run(self, **k):
        self.seen.append(k)
        nxt = self.outcomes.pop(0)

        def wait():
            if isinstance(nxt, BaseException):
                raise nxt
            asyncio.run(self._start_operation(SimpleNamespace(command=k["shell"])))
            if isinstance(nxt, tuple):
                raise nxt[1]
            return nxt
        return SimpleNamespace(wait=wait)


def _client(outcomes, seen):
    return _Client(outcomes, seen)


def _sess(outcomes, retry=True):
    seen = []
    s = cs.ContreeSession(retry_transient=retry)
    s._client = _client(outcomes, seen)
    return s, seen, None


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(cs, "_sleep", slept.append)
    monkeypatch.setattr(cs, "_sdk_version", lambda: cs.SUPPORTED_SDK_VERSION)
    return slept


def _ok():
    return SimpleNamespace(exit_code=0, stdout="ready\n", stderr="", uuid="img-1")


def test_timeout_then_success(no_sleep):
    s, seen, _ = _sess([ApiTimeoutError(), _ok()])
    got = s.checkpoint_main("true", timeout=60)
    assert got["uuid"] == "img-1" and len(seen) == 2
    assert no_sleep == [cs.RETRY_DELAYS[0]]


def test_5xx_then_success(no_sleep):
    s, seen, _ = _sess([ServerError(), ServerError(), _ok()])
    assert s.run_op("base", "true", disposable=False)["exit_code"] == 0
    assert len(seen) == 3 and no_sleep == list(cs.RETRY_DELAYS)


def test_repeated_timeouts_keep_original_reason(no_sleep):
    s, seen, _ = _sess([ApiTimeoutError() for _ in range(5)])
    with pytest.raises(cs.ContreeError) as e:
        s.checkpoint_main("true", timeout=60)
    assert str(e.value) == "contree request failed: ApiTimeoutError"
    assert len(seen) == cs.MAX_TRIES == 3 and len(no_sleep) == 2


def test_auth_refusal_and_other_errors_are_not_retried():
    for exc, auth in ((Forbidden(), True), (ValueError("bad"), False)):
        s, seen, _ = _sess([exc, _ok()])
        with pytest.raises(cs.ContreeError) as e:
            s.run_op("base", "true", disposable=False)
        assert len(seen) == 1 and e.value.auth is auth


def test_no_retry_off_the_product_route(no_sleep):
    s, seen, _ = _sess([ApiTimeoutError(), _ok()], retry=False)
    with pytest.raises(cs.ContreeError, match="ApiTimeoutError"):
        s.run_op("base", "true", disposable=False)
    assert len(seen) == 1 and no_sleep == []


def test_product_route_asks_for_retry_and_never_runs_locally(monkeypatch, tmp_path):
    from ops import daily_run
    seen = {}

    def prep(*args, **kw):
        seen.update(kw)
        raise cs.ContreeError("contree request failed: ApiTimeoutError")
    monkeypatch.setattr(cs, "prepare_source_pair", prep)
    monkeypatch.setattr(daily_run, "run", lambda *a, **k: pytest.fail("ran locally"))
    a = SimpleNamespace(sandbox_backend="contree", product_check=True, pr=1, bench=None)
    rec = {"files": {"all": []}}
    why = daily_run._maybe_prepare_contree(a, "o/r", "a" * 40, "b" * 40, rec, 60)
    assert seen.get("retry_transient") is True
    assert why and "contree request failed: ApiTimeoutError" in why
    assert rec["contree"]["failed"] == "contree request failed: ApiTimeoutError"


def test_wait_timeout_after_start_never_starts_a_second_run(no_sleep):
    """The run is created, then waiting on it times out: exactly one run, original reason, no retry."""
    s, seen, _ = _sess([("wait", ApiTimeoutError()), _ok(), _ok()])
    with pytest.raises(cs.ContreeError) as e:
        s.checkpoint_main("true", timeout=60)
    assert str(e.value) == "contree request failed: ApiTimeoutError"
    assert len(s._client.created) == 1 and len(seen) == 1 and no_sleep == []


def test_5xx_while_waiting_is_not_retried(no_sleep):
    s, seen, _ = _sess([("wait", ServerError()), _ok()])
    with pytest.raises(cs.ContreeError):
        s.run_op("base", "true", disposable=False)
    assert len(s._client.created) == 1 and no_sleep == []


def test_start_failures_retry_and_create_one_run(no_sleep):
    s, seen, _ = _sess([ApiTimeoutError(), ServerError(), _ok()])
    assert s.run_op("base", "true", disposable=False)["exit_code"] == 0
    assert len(s._client.created) == 1 and len(seen) == 3


def test_deadline_skips_a_retry_when_time_left_is_short(monkeypatch, no_sleep):
    clock = [1000.0]
    monkeypatch.setattr(cs, "_now", lambda: clock[0])
    s, seen, _ = _sess([ApiTimeoutError(), _ok()])

    def slow_use(ref, strict=True):  # the failed start itself took most of the grace window
        clock[0] += cs.RETRY_GRACE
        return s._client.images.oci(ref)
    img_use = s._client.images.use
    s._client.images.use = slow_use
    s.main_uuid = "main-1"
    with pytest.raises(cs.ContreeError, match="ApiTimeoutError"):
        s.run_op("main", "true", timeout=600)
    assert len(seen) == 1 and no_sleep == [] and s._client.created == []
    s._client.images.use = img_use


def test_no_create_hook_means_no_retry(no_sleep):
    """If the SDK does not expose run creation we cannot tell a start failure from a wait failure: fail closed."""
    s, seen, _ = _sess([ApiTimeoutError(), _ok()])
    s._client = SimpleNamespace(images=s._client.images)
    with pytest.raises(cs.ContreeError):
        s.run_op("base", "true", disposable=False)
    assert len(seen) == 1 and no_sleep == []


@pytest.mark.parametrize("ver", [None, "0.3.5", "0.3.7", "0.4.0", "0.3.6.post1"])
def test_retries_only_on_the_checked_sdk_version(monkeypatch, no_sleep, ver):
    """The start hook was checked only on contree-sdk 0.3.6; any other or missing version fails closed (no retry)."""
    monkeypatch.setattr(cs, "_sdk_version", lambda: ver)
    s, seen, _ = _sess([ApiTimeoutError(), _ok()])
    with pytest.raises(cs.ContreeError):
        s.run_op("base", "true", disposable=False)
    assert len(seen) == 1 and no_sleep == []
    assert not getattr(s._client, "_poc_tracks_starts", False)


def test_checked_sdk_version_retries(no_sleep):
    assert cs._sdk_version() == "0.3.6"
    s, seen, _ = _sess([ApiTimeoutError(), _ok()])
    assert s.run_op("base", "true", disposable=False)["exit_code"] == 0
    assert len(seen) == 2


def test_transport_error_before_start_is_retried(no_sleep):
    s, seen, _ = _sess([ContreeTransportError(), _ok()])
    got = s.checkpoint_main("true", timeout=60)
    assert got["uuid"] == "img-1" and len(seen) == 2
    assert no_sleep == [cs.RETRY_DELAYS[0]]


def test_transport_error_after_start_is_not_retried(no_sleep):
    s, seen, _ = _sess([("wait", ContreeTransportError()), _ok()])
    with pytest.raises(cs.ContreeError, match="ContreeTransportError"):
        s.checkpoint_main("true", timeout=60)
    assert len(s._client.created) == 1 and no_sleep == []


def test_client_uses_a_long_http_timeout(monkeypatch):
    from dataclasses import fields

    from contree_sdk.auth import IAMAuth

    captured = {}

    class FakeSync:
        def __init__(self, config=None, **kwargs):
            captured["config"] = config
            captured["kwargs"] = kwargs

    import contree_sdk
    monkeypatch.setattr(contree_sdk, "ContreeSync", FakeSync)
    client = cs.ContreeSession()._client_sync()
    cfg = captured["config"]
    token_default = next(f for f in fields(IAMAuth) if f.name == "token").default
    assert client is not None and captured["kwargs"] == {}
    assert cfg.transport_timeout == cs.HTTP_TIMEOUT >= 60
    assert isinstance(cfg.auth, IAMAuth) and cfg.auth.token == token_default


def _stop_item():
    return {
        "pr": 43, "url": "https://example/43", "title": "t", "body": "", "diff": "",
        "head_sha": "b" * 40, "base_sha": "c" * 40, "author": "a", "base_ref": "main",
        "updated_at_utc": "2026-01-01T00:00:00Z", "updated_at_ist": "2026-01-01 05:30 IST",
        "ci_state": "none", "ci_detail": "",
        "files": {"all": [], "package_py": [], "compiled": [], "other": []},
    }


def _stop_args(product):
    return SimpleNamespace(
        product_check=product, pr="https://example/43" if product else None, bench=None,
        runs=1, workers=1, test_timeout=60, run_timeout=60, build_timeout=60,
        python="3.12", python_full=None, baseline="full", sandbox_backend="contree",
        sandbox_backend_note=None, swarm=False, provider=None, model_provider=None,
        model_note=None, model_skipped=None, model_fallback=None, poc_commit="a" * 40,
        invocation=None, tool_setup={"note": "test"})


def test_product_contree_failure_is_could_not_verify(monkeypatch, tmp_path):
    from ops import daily_run
    monkeypatch.setattr(daily_run, "finish", lambda rec, prdir, work, t0, runner=None: rec)
    rec = daily_run.record_contree_failure(
        "mahmoud/boltons", {"pkg": "boltons", "dist": "boltons"}, _stop_item(),
        tmp_path, tmp_path, _stop_args(True), {}, cs.ContreeError("contree request failed: ApiTimeoutError"))
    assert rec["verdict"] == "could_not_verify"
    assert "ApiTimeoutError" in rec["reason"]
    assert rec["product_check"] is True and rec["contree"]["fallback"] is None


def test_study_contree_failure_stays_a_harness_error():
    from ops import daily_run
    got = daily_run.record_contree_failure(
        "mahmoud/boltons", {"pkg": "boltons", "dist": "boltons"}, _stop_item(),
        Path("unused"), Path("unused"), _stop_args(False), {},
        cs.ContreeError("contree request failed: ApiTimeoutError"))
    assert got is None


def test_sdk_version_reads_installed_metadata(monkeypatch):
    import importlib.metadata as md

    monkeypatch.setattr(md, "version", lambda name: "9.9.9" if name == "contree-sdk" else "0")
    assert _REAL_SDK_VERSION() == "9.9.9"

    def missing(name):
        raise md.PackageNotFoundError(name)

    monkeypatch.setattr(md, "version", missing)
    assert _REAL_SDK_VERSION() is None
