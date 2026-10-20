"""Tests for the model-reply and comparison-runner fixes: empty answers, probe names, per-case routing, timeouts."""
import io
import json
import sys

import pytest

from evals import patchguru_runner as pg
from ops import bench
from ops import daily_run as dr
from poc import model_probes, model_provider
from poc.leakage import Fingerprints
from poc.model_gate import Gate


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _reply(content, finish):
    return _Resp(json.dumps({"model": "nvidia/x", "usage": {"completion_tokens": 8000},
                             "choices": [{"finish_reason": finish, "message": {"content": content}}]}).encode())


# (1) empty answer at the token limit -> clear ProviderError, not a bare TypeError
def test_empty_answer_at_length_gives_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(model_provider.urllib.request, "urlopen", lambda req, timeout=None: _reply(None, "length"))
    monkeypatch.setenv("POC_RAW_DIR", str(tmp_path))
    p = model_provider.NebiusProvider("k")
    with pytest.raises(model_provider.ProviderError) as e:
        p.complete_json("probes", "s", "u", {}, {})
    assert "finish_reason=length" in str(e.value) and "TypeError" not in str(e.value)
    saved = json.loads(next(tmp_path.glob("*-probes-*.json")).read_text())
    assert saved["finish_reason"] == "length" and saved["server_model"] == "nvidia/x"


def test_default_token_limit_is_32k(monkeypatch):
    seen = {}

    def fake(req, timeout=None):
        seen.update(json.loads(req.data))
        return _reply('{"ok": true}', "stop")
    monkeypatch.setattr(model_provider.urllib.request, "urlopen", fake)
    monkeypatch.delenv("POC_MAX_TOKENS", raising=False)
    assert model_provider.NebiusProvider("k").complete_json("claims", "s", "u", {}, {}) == {"ok": True}
    assert seen["max_tokens"] == 32000


# (2) probe names like 'P1' / 'probe_get_x' are tidied, not rejected
CLAIM = {"claims": [{"id": "C1", "text": "f changes", "source_quote": "f now changes", "testable": True,
                     "expect": "differs"}]}
CODE = "import json\nprint(json.dumps({'observations': {'f.a': 1}}))\n"


class Scripted(model_provider.Provider):
    name = "scripted"

    def __init__(self, probes):
        super().__init__()
        self.probes = probes

    def complete_json(self, task, system, user, schema, ctx):
        return CLAIM if task == "claims" else {"probes": self.probes}


@pytest.mark.parametrize("raw_id,tidy", [("P1", "p1"), ("probe_get_x", "probe-get-x")])
def test_probe_names_are_normalised(tmp_path, raw_id, tidy):
    base = tmp_path / "base"
    (base / "pkg").mkdir(parents=True)
    (base / "pkg" / "m.py").write_text("def f(x):\n    return x\n")
    probe = {"id": raw_id, "about": "f", "claims": [{"id": "C1", "covers": ["f.*"], "expect": "differs"}],
             "code": CODE}
    out = model_probes.generate(Scripted([probe]), "o/r", 1, "Change f", "f now changes",
                                {"pkg/m.py": base / "pkg" / "m.py"}, base, [tmp_path / "pr"], tmp_path / "out")
    assert not out["errors"] and [p["path"].name for p in out["probes"]] == [f"model-{tidy}.py"]


# (3) each PatchGuru case uses its own settings and raw folder
def _server(model):
    return lambda body: {"model": model, "choices": [{"message": {"content": "ok"}}]}


def test_each_case_routes_to_its_own_chat(tmp_path):
    a = pg.NebiusChat(Gate.no_answer_key(pr="o/r#1"), "m", tmp_path / "A", "k", transport=_server("ma"))
    b = pg.NebiusChat(Gate.no_answer_key(pr="o/r#2"), "m", tmp_path / "B", "k", transport=_server("mb"))
    pg.install_query_llm(a)
    query = sys.modules["patchguru.llms.OpenAI"].query_llm   # held by name, as PatchGuru's modules do
    query("first case")
    pg.install_query_llm(b)
    query("second case")
    assert len(a.calls) == 1 and len(b.calls) == 1
    assert list((tmp_path / "B").glob("*.json")) and b.gate.log[0]["ok"] and b.gate.pr == "o/r#2"
    assert a.summary()["server_models"] == ["ma"] and b.summary()["server_models"] == ["mb"]


# (4) a model timeout -> could_not_verify for that case only; the run continues
def test_timeout_is_recorded_and_run_continues(tmp_path, monkeypatch):
    rows = [{"id": "B90", "repo": "o/r", "pr": "1"}, {"id": "B91", "repo": "o/r", "pr": "2"}]
    monkeypatch.setattr(bench, "read_inputs", lambda p: rows)
    monkeypatch.setattr(bench, "select", lambda r, ids: r)
    monkeypatch.setattr(dr, "resolve_python", lambda s: s)
    monkeypatch.setattr(dr, "detect_machine_type", lambda: {})
    fpf = tmp_path / "fp.json"
    fpf.write_text(json.dumps(Fingerprints(source="t").to_json()))
    monkeypatch.setenv(pg.KEY_ENV, "k")
    monkeypatch.setattr(model_provider.NebiusProvider, "confirm_key", lambda self: None)
    done = []

    def fake_case(row, a, fp, key, out, machine):
        if row["id"] == "B90":
            raise TimeoutError("The read operation timed out")
        done.append(row["id"])
        return [{"baseline": b, "verdict": "verified", "reason": "ok", "label": "blind"} for b in pg.BASELINES]
    monkeypatch.setattr(pg, "run_case", fake_case)
    out = tmp_path / "out"
    assert pg.main(["--bench", "x.csv", "--patchguru", str(tmp_path), "--fingerprints", str(fpf),
                    "--out", str(out)]) == 0
    assert done == ["B91"]
    for bl in ("patchguru_pre_review", "patchguru_post_review"):
        r = json.loads((out / f"B90-{bl}.json").read_text())
        assert r["verdict"] == "could_not_verify" and "TimeoutError" in r["reason"] and r["label"] == "pilot"
