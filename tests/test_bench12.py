"""Known-answer benchmark (evals/bench12) and the AI-probe gate in the golden re-derivation (evals/checks)."""
from __future__ import annotations

import builtins
import json
import re
from pathlib import Path

import pytest

from evals.bench12 import run_case as rc
from evals.bench12.score import score
from evals.checks import derive_verdict
from ops import daily_run as dr
from poc import probes

BENCH = Path(__file__).resolve().parents[1] / "evals" / "bench12"


@pytest.mark.parametrize("row", score(), ids=lambda r: f"{r['case']}-{r['baseline']}-{r['route']}")
def test_case_matches_answer_key(row):
    assert row["actual"] == row["expected"], row["reason"]
    assert row["golden"] in (None, row["expected"]), "golden re-derivation disagrees with the real gates"


def test_every_case_folder_is_scored():
    keyed = {r["case"] for r in score()}
    assert keyed == {p.name for p in (BENCH / "cases").iterdir() if p.is_dir()}


LABELS = re.compile(r"verified|needs[\s_-]*attention|could[\s_-]*not[\s_-]*verify|no[\s_-]*code[\s_-]*change|skipped",
                    re.IGNORECASE)


def _case_files():
    return [p for case in (BENCH / "cases").iterdir() for p in case.rglob("*") if p.is_file()]


def test_case_files_carry_no_hint_of_the_answer():
    key = json.loads((BENCH / "answer_key.json").read_text())
    expected = {e["expected"] for e in key["answers"]}
    assert _case_files()
    for p in _case_files():
        text = p.read_text()
        for where in (str(p.relative_to(BENCH)), text):
            assert not re.search(r"answer|expected", where, re.IGNORECASE), p
            assert not LABELS.search(where), f"{p} names a verdict label"
            assert not any(v.lower() in where.lower() for v in expected), p


def test_run_case_never_opens_the_answer_key(monkeypatch):
    with pytest.raises(ValueError):
        rc.run_case(BENCH / "answer_key.json")
    opened: list[str] = []
    real_open, real_read = builtins.open, Path.read_text

    def spy_open(f, *a, **k):
        opened.append(str(f))
        return real_open(f, *a, **k)

    def spy_read(self, *a, **k):
        opened.append(str(self))
        return real_read(self, *a, **k)

    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(Path, "read_text", spy_read)
    for case in sorted((BENCH / "cases").iterdir()):
        for bl, route in (("full", "single"), ("tests", "single"), ("full", "daily")):
            rc.run_case(case, bl, route)
    assert opened and not [f for f in opened if "answer" in f.lower()]


# ---- AI-probe gate in derive_verdict -------------------------------------------------------------------------
PKG = {"all": ["toypkg/__init__.py"], "package_py": ["toypkg/__init__.py"], "compiled": [], "other": []}
DOCS = {"all": ["README.md"], "package_py": [], "compiled": [], "other": ["README.md"]}


def _rec(files=PKG, covered=1, source="model", probe=True, docstring_only=False):
    runs = {"main": [{"tests/t.py::test_a": ("passed", "")}] * 3, "pr": [{"tests/t.py::test_a": ("passed", "")}] * 3}
    rec = {"files": files, "comparison": dr.compare_sides(runs), "behaviour_claims": [],
           "docstring_only": docstring_only,
           "coverage": {"status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1}
           if files is PKG else {"status": "not measured", "why": "no changed python"}}
    if probe:
        spec = {"id": "p1", "target": "toypkg", "about": "x", "claims": [{"id": "C1", "expect": "differs",
                                                                         "covers": ["v"]}]}
        r = {"main": [{"v": 1}] * 3, "pr": [{"v": 2}] * 3}
        rec["probes"] = probes.apply_status({"items": [{**spec, "source": source, "status": "ran", "runs": r,
                                                        "observations": probes.judge(spec, r),
                                                        "probe_changed_line_coverage": {
                                                            "status": "measured", "changed_lines_total": 1,
                                                            "changed_lines_covered": covered}}]})
    return rec


def test_gate_keeps_verified_when_model_probe_ran_a_changed_line():
    assert derive_verdict(_rec(), "full") == "verified"


@pytest.mark.parametrize("kw", [dict(covered=0), dict(source="library"), dict(probe=False)])
def test_gate_demotes_verified_without_a_model_probe_on_a_changed_line(kw):
    assert derive_verdict(_rec(**kw), "full") == "could_not_verify"
    assert derive_verdict(_rec(**kw), "tests") == "verified"


def test_docs_only_and_docstring_only_never_full_mode_verified():
    assert derive_verdict(_rec(files=DOCS, probe=False), "full") == "could_not_verify"
    assert derive_verdict(_rec(probe=False, docstring_only=True), "full") == "could_not_verify"
    assert derive_verdict(_rec(covered=0, docstring_only=True), "full") == "could_not_verify"


@pytest.mark.parametrize("kw", [dict(), dict(covered=0), dict(files=DOCS, probe=False), dict(docstring_only=True)])
def test_derive_matches_real_gate(kw):
    rec = _rec(**kw) | {"baseline": "full"}
    dr._store_verdict(rec, rec["comparison"], None, None)
    assert derive_verdict(rec, "full") == dr.gate(rec)["verdict"]
