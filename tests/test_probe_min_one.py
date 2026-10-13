"""At least one probe per testable claim: prompt rule, schema minItems, and one retry on an empty/unusable answer."""
from pathlib import Path

from poc import model_probes, model_provider

TITLE = "Fix format specifiers in f"
BODY = "f now formats its name correctly."
CLAIM = {"claims": [{"id": "C1", "text": "f formats its name correctly", "source_quote": "f now formats its name "
                     "correctly", "testable": True, "expect": "differs"}]}
GOOD = {"probes": [{"id": "P1", "about": "f", "claims": [{"id": "C1", "covers": ["f.*"], "expect": "differs"}],
                    "code": "import json\nprint(json.dumps({'observations': {'f.a': 1}}))\n"}]}


class Scripted(model_provider.Provider):
    name = "scripted"

    def __init__(self, probe_answers):
        super().__init__()
        self.answers, self.prompts = list(probe_answers), []

    def complete_json(self, task, system, user, schema, ctx):
        self.prompts.append((task, user))
        return CLAIM if task == "claims" else self.answers.pop(0)


def _run(tmp_path, answers):
    base = tmp_path / "base"
    (base / "pkg").mkdir(parents=True)
    (base / "pkg" / "m.py").write_text("def f(x):\n    return x\n")
    prov = Scripted(answers)
    out = model_probes.generate(prov, "o/r", 1, TITLE, BODY, {"pkg/m.py": base / "pkg" / "m.py"}, base,
                                [tmp_path / "pr"], tmp_path / "out")
    return prov, out


def test_prompt_and_schema_require_a_probe():
    assert "empty \"probes\" list is not an acceptable answer" in model_provider.PROBES_PROMPT
    assert model_provider.PROBES_SCHEMA["properties"]["probes"]["minItems"] == 1


def test_empty_answer_is_retried_once(tmp_path):
    prov, out = _run(tmp_path, [{"probes": []}, GOOD])
    assert [t for t, _ in prov.prompts] == ["claims", "probes", "probes"]
    assert "no usable probe" in prov.prompts[-1][1] and out["retried"]
    assert len(out["probes"]) == 1 and out["probes"][0]["path"].name == "model-p1.py"


def test_good_first_answer_is_not_retried(tmp_path):
    prov, out = _run(tmp_path, [GOOD])
    assert [t for t, _ in prov.prompts] == ["claims", "probes"] and "retried" not in out


def test_retry_happens_at_most_once(tmp_path):
    prov, out = _run(tmp_path, [{"probes": []}, {"probes": []}])
    assert len(prov.prompts) == 3 and out["probes"] == []


def test_retry_prompt_has_no_pr_side_or_answer_text(tmp_path):
    prov, _ = _run(tmp_path, [{"probes": []}, GOOD])
    retry = prov.prompts[-1][1]
    assert retry.startswith(prov.prompts[1][1]) and Path(tmp_path / "pr").as_posix() not in retry


def test_no_testable_claims_still_asks_for_a_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(Scripted, "complete_json", lambda self, task, system, user, schema, ctx: (
        self.prompts.append((task, user)) or ({"claims": []} if task == "claims" else self.answers.pop(0))))
    nc = {"probes": [dict(GOOD["probes"][0], claims=[])]}
    prov, out = _run(tmp_path, [nc])
    assert out.get("no_claims_probe") and len(out["probes"]) == 1
    assert "none were testable" in prov.prompts[-1][1]


def test_double_escaped_code_is_unescaped():
    one_line = "import json\\nprint(json.dumps({\\\"observations\\\": {\\\"a\\\": 1}}))\\n"
    fixed = model_probes._unescape_code(one_line)
    assert "\n" in fixed and "json.dumps" in fixed
    good = "x = 'a\\nb'\n"
    assert model_probes._unescape_code(good) == good
