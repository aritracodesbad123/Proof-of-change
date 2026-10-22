"""Product checks retry a transient Contree API timeout or 5xx, at most 3 tries, and never run locally."""
from types import SimpleNamespace

import pytest

from poc import contree_sandboxes as cs


class ApiTimeoutError(Exception):
    pass


class ServerError(Exception):
    status_code = 503


class Forbidden(Exception):
    pass


def _client(outcomes, seen):
    """Fake ContreeSync whose run().wait() pops the next outcome (an exception to raise, or a result)."""
    def run(**k):
        seen.append(k)
        nxt = outcomes.pop(0)
        if isinstance(nxt, BaseException):
            raise nxt
        return SimpleNamespace(wait=lambda: nxt)
    img = SimpleNamespace(run=run)
    return SimpleNamespace(images=SimpleNamespace(oci=lambda ref: img, use=lambda ref, strict=True: img))


def _sess(outcomes, retry=True):
    seen = []
    s = cs.ContreeSession(retry_transient=retry)
    s._client = _client(outcomes, seen)
    return s, seen, None


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(cs, "_sleep", slept.append)
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
