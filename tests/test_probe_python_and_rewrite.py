"""Probe syntax is checked with the Python that runs the probe, and a probe that crashed on main gets one rewrite
that can never raise the verdict."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ops import daily_run
from poc import contree_sandboxes, freeze, model_probes, probe_python, probes

MATCH = "match x:\n    case 1:\n        pass\n"


def test_grammar_error_uses_the_target_version():
    assert probe_python.grammar_error(MATCH, "3.9")
    assert probe_python.grammar_error(MATCH, "3.10") is None


@pytest.mark.skipif(sys.version_info < (3, 14), reason="t-strings need a 3.14 parser")
def test_t_string_is_rejected_for_3_12():
    assert probe_python.grammar_error("x = t'hi'\n", "3.12")
    assert probe_python.grammar_error("x = t'hi'\n", "3.14") is None


def test_choose_keeps_default_when_it_fits():
    got = probe_python.choose([">=3.8"], ["3.12", "3.13"], {"a.py": MATCH}, "3.12", ["3.10", "3.12", "3.13"])
    assert got["version"] == "3.12"


def test_choose_takes_newest_listed_fit_and_states_why():
    got = probe_python.choose([">=3.13"], ["3.13"], {}, "3.12", ["3.12", "3.13", "3.14"])
    assert got["version"] == "3.13"
    assert "3.12" in got["why"]


def test_choose_refuses_plainly_when_nothing_fits():
    got = probe_python.choose([">=3.15"], [], {}, "3.12", ["3.12", "3.13"])
    assert got["version"] is None
    assert got["why"].startswith("not runnable here")


def test_image_for_swaps_only_the_version():
    assert probe_python.image_for("3.11", "docker.io/library/python:3.12-slim-bookworm") == \
        "docker.io/library/python:3.11-slim-bookworm"


def test_pick_selects_image_and_refusal_stops_contree(tmp_path, monkeypatch):
    main = tmp_path / "main"
    main.mkdir()
    (main / "pyproject.toml").write_text('[project]\nname="x"\nrequires-python=">=3.13"\n')
    monkeypatch.setattr(contree_sandboxes, "BASE_IMAGE", "docker.io/library/python:3.12-slim")
    monkeypatch.setenv(probe_python.PYTHONS_ENV, "3.12,3.13")
    rec = {"files": {"all": []}}
    try:
        pick = daily_run._pick_contree_python(rec, main, None)
        assert pick["version"] == "3.13" and contree_sandboxes.image_python() == "3.13"
        rec2 = {"files": {"all": []}, "contree_python": {"version": None, "why": "not runnable here: x"}}
        a = SimpleNamespace(sandbox_backend="contree", product_check=True, pr=1, bench=None)
        assert daily_run._maybe_prepare_contree(a, "o/r", "m", "p", rec2, 10) == "not runnable here: x"
    finally:
        contree_sandboxes.select_image(None)


def test_validate_probe_checks_target_grammar():
    p = {"id": "p1", "code": MATCH + "print(1)\n", "claims": []}
    assert model_probes.validate_probe(p, set(), "3.9")
    assert "Python version: the probes run on Python 3.12" in model_probes.python_rule("3.12")


class FakeProvider:
    def __init__(self, code):
        self.code, self.calls = code, []

    def complete_json(self, kind, prompt, user, schema, ctx):
        self.calls.append((prompt, user))
        return {"probes": [{"id": "p1", "about": "a", "claims": [], "code": self.code}]}


def _crashed_item(prdir: Path):
    gen = freeze.generator("model", model="m", provider="nebius")
    path = prdir / "model-p1.py"
    path.write_text(model_probes.probe_file({"id": "p1", "about": "a", "claims": [], "code": "boom()\n"},
                                            "o/r#1", {}, gen["label"]))
    err = {probes.PROBE_ERROR: "NameError: boom"}
    return {"id": "model-p1", "source": "model", "path": path.name, "runs": {"main": [err, err], "pr": [err, err]},
            "files": {"main": []}, "freeze": freeze.freeze(path, gen, None)}


def test_crashed_probe_gets_exactly_one_rewrite_with_the_error(tmp_path):
    items = [_crashed_item(tmp_path)]
    prov = FakeProvider("import json\nprint(json.dumps({'observations': {'x': 1}}))\n")
    ran = []

    def run_one(x, started):
        ran.append(x)
        freeze.verify(Path(x["path"]), x["freeze"], started)
        return {"id": "model-p1-rewrite", "source": "model", "path": Path(x["path"]).name,
                "runs": {"main": [{"x": 1}], "pr": [{"x": 1}]}}

    out = daily_run.rewrite_crashed_probes(items, tmp_path, SimpleNamespace(provider=prov), run_one)
    assert len(prov.calls) == 1 and len(ran) == 1
    assert "NameError: boom" in prov.calls[0][1] and "pytester" in prov.calls[0][0]
    assert items[0]["rewrite_of"] == "model-p1" and out["before"][0]["id"] == "model-p1"
    assert (tmp_path / "model-p1-rewrite.py").read_text().count("'id': 'model-p1-rewrite'") == 1


@pytest.mark.parametrize("with_rw,without,final", [
    ("verified", "could_not_verify", "could_not_verify"),
    ("could_not_verify", "needs_attention", "needs_attention"),
    ("needs_attention", "could_not_verify", "needs_attention"),
    ("verified", "verified", "verified"),
])
def test_rewrite_can_never_raise_the_verdict(monkeypatch, with_rw, without, final):
    import evals.checks
    monkeypatch.setattr(evals.checks, "derive_verdict", lambda rec, baseline, pp=None: without)
    rec = {"verdict": with_rw, "reason": "r", "probes": {"items": [], "rewrite": {"before": [], "probes": []}}}
    out = daily_run.cap_rewrite(rec)
    assert out["verdict"] == final
    assert daily_run.VERDICT_RANK[out["verdict"]] <= daily_run.VERDICT_RANK[without]


def test_no_rewrite_leaves_the_record_alone():
    rec = {"verdict": "verified", "probes": {"items": []}}
    assert daily_run.cap_rewrite(dict(rec)) == rec
