"""Three fixes checked against the 2026-10-31 daily records, offline.

loguru #1536: collection failed because conftest imports freezegun, and freezegun is only in the dev extra.
sqlparse #941: two claim quotes were rejected because they were not the pull request text character for character.
toolz #654: model probes exited 0 and were saved as non-json output.
"""
from __future__ import annotations

from types import SimpleNamespace

from ops import daily_run
from poc import demo_helper, model_probes, probes

# The two quotes the sqlparse record rejected, and the sentences they were copied from.
SQLPARSE_BODY = (
    'The output for the reported input is now the input unchanged (`"( AS )"`).\n'
    "Behaviour for well-formed groups is unchanged — `SELECT ( a ) FROM t` still formats to "
    "`SELECT (a) FROM t`, and the full suite passes.\n"
)
SQLPARSE_QUOTES = [
    {"id": "C1", "expect": "differs", "testable": True,
     "source_quote": "The output for the reported input is now the input unchanged ('( AS )')."},
    {"id": "C2", "expect": "same", "testable": True,
     "source_quote": "Behaviour for well-formed groups is unchanged — SELECT ( a ) FROM t still formats to "
                     "SELECT (a) FROM t"},
]
# A print of a dict, the shape that was saved as crash "non-json output" with exit code 0.
TOOLZ_PRINT = "{'observations': {'before': [0, 1, 2, 3], 'after': [3, 2, 1, 0]}}"
LOGURU_REASON = (
    "probe: 1 observation(s) need attention: c5.default_newline_follows_os_linesep differs and no claim covers it; "
    "tests: tests produced no results on one side (collection failed; see pytest logs)"
)


def _loguru_tree(root):
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "loguru"\n'
        "dependencies = [\"colorama>=0.3.4 ; sys_platform=='win32'\"]\n\n"
        "[project.optional-dependencies]\n"
        "dev = [\"freezegun==1.5.0 ; python_version>='3.8'\", \"sphinx\"]\n")
    tests = root / "tests"
    tests.mkdir()
    (tests / "conftest.py").write_text("import freezegun\nimport pytest\n")
    return root


def _installed(root):
    return [item["name"] for item in demo_helper.declared_packages(root, "loguru") if item["action"] == "install"]


def test_dev_extra_is_installed_when_no_extra_is_named_test(tmp_path):
    root = _loguru_tree(tmp_path / "loguru")
    assert "freezegun" in _installed(root) and "sphinx" in _installed(root)
    assert "colorama" not in _installed(root)
    assert daily_run.pyproject_test_extras(root) == ["dev"]
    assert daily_run.with_test_extras(["-e", str(root)], root) == ["-e", f"{root}[dev]"]
    assert daily_run.test_extras(["docs", "dev"]) == ["dev"]
    assert daily_run.test_extras(["test", "dev"]) == ["test"]


def test_a_test_extra_still_wins_over_dev(tmp_path):
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\n[project.optional-dependencies]\n'
        'test = ["pytest"]\ndev = ["sphinx"]\n')
    (root / "conftest.py").write_text("import sphinx\n")
    names = [item["name"] for item in demo_helper.declared_packages(root, "pkg") if item["action"] == "install"]
    assert names == ["pytest"]
    assert daily_run.pyproject_test_extras(root) == ["test"]


def test_an_extra_conftest_imports_is_installed_when_it_is_not_named_dev(tmp_path):
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\n[project.optional-dependencies]\n'
        'ci = ["freezegun==1.5.0"]\n')
    (root / "conftest.py").write_text("import freezegun\n")
    assert "freezegun" in _installed(root)
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\n[project.optional-dependencies]\nci = ["freezegun==1.5.0"]\n')
    assert _installed(bare) == []


def test_collection_import_is_a_setup_gap_and_the_study_retry_installs_it():
    rec = {"verdict": "needs_attention", "reason": LOGURU_REASON,
           "per_run": [{"pytest_summary": "E   ModuleNotFoundError: No module named 'freezegun'"}]}
    assert demo_helper.collection_import_gap(demo_helper.gap_text(rec))
    assert demo_helper.gap_name(demo_helper.gap_text(rec)) == "freezegun"
    calls = []
    demo_helper.retry_unverified_study(
        rec, lambda: calls.append("rerun") or {"verdict": "needs_attention", "reason": "probe: c5 differs; tests ran"},
        lambda side, requirement: calls.append((side, requirement)) or (True, "1.5.0"),
        ["freezegun==1.5.0 ; python_version>='3.8'"], "", None, "Delgan/loguru")
    assert calls[:2] == [("main", "freezegun==1.5.0 ; python_version>='3.8'"),
                         ("pr", "freezegun==1.5.0 ; python_version>='3.8'")]
    assert calls[-1] == "rerun"
    assert rec["verdict"] == "needs_attention" and "collection failed" not in rec["reason"]


def test_a_needs_attention_import_that_is_not_collection_is_not_retried():
    attention = {"verdict": "needs_attention", "reason": "ModuleNotFoundError: No module named 'numpy'"}
    demo_helper.retry_unverified_study(
        attention, lambda: (_ for _ in ()).throw(AssertionError("rerun")),
        lambda *_a: (_ for _ in ()).throw(AssertionError("install")),
        ["numpy"], "", None, "acme/widget")
    assert attention["verdict"] == "needs_attention"


def test_an_unrepaired_collection_import_keeps_the_recorded_verdict():
    rec = {"verdict": "needs_attention", "reason": LOGURU_REASON,
           "per_run": [{"pytest_summary": "E   ModuleNotFoundError: No module named 'freezegun'"}]}
    demo_helper.retry_unverified_study(
        rec, lambda: (_ for _ in ()).throw(AssertionError("rerun")),
        lambda *_a: (_ for _ in ()).throw(AssertionError("install")),
        [], "", None, "Delgan/loguru")
    assert rec["verdict"] == "needs_attention" and "collection failed" in rec["reason"]


def test_study_collection_gap_reads_extras_from_the_checkout(tmp_path, monkeypatch):
    root = _loguru_tree(tmp_path / "src")
    seen = {}

    def fake_retry(rec, rerun, install_one, declared, *args, **kwargs):
        seen["declared"] = list(declared)
        return rec

    monkeypatch.setattr(demo_helper, "retry_unverified_study", fake_retry)
    a = SimpleNamespace(bench=None, pr="https://github.com/Delgan/loguru/pull/1536", product_check=False)
    rec = {"verdict": "needs_attention", "reason": LOGURU_REASON,
           "per_run": [{"pytest_summary": "E   ModuleNotFoundError: No module named 'freezegun'"}],
           "demo_helper": {"setup_plan": {"packages": []}, "tavily": {}}}
    daily_run._retry_setup_gap(a, rec, "Delgan/loguru", tmp_path, {}, None, checkouts=[root])
    assert any(str(req).startswith("freezegun") for req in seen["declared"])


def test_sqlparse_loose_quotes_keep_markdown_and_a_changed_quote_mark():
    raw = {"claims": SQLPARSE_QUOTES}
    title = "Don't raise IndexError on short parenthesis groups in StripWhitespaceFilter"
    exact, _ = model_probes.grounded_claims(raw, title, SQLPARSE_BODY)
    assert exact == []
    kept, rejected = model_probes.grounded_claims(raw, title, SQLPARSE_BODY, loose=True)
    assert [c["id"] for c in kept] == ["C1", "C2"] and rejected == []
    assert all(c["quote_match"] == "loose" for c in kept)


def test_study_route_grounds_quotes_loosely(tmp_path):
    body = SQLPARSE_BODY

    class P:
        calls = []

        def describe(self):
            return "fake"

        def complete_json(self, kind, *args, **kwargs):
            if kind == "claims":
                return {"claims": [dict(c, testable=False) for c in SQLPARSE_QUOTES]}
            return {"probes": []}

    out = model_probes.generate(P(), "andialbrecht/sqlparse", 941, "t", body, {}, tmp_path, [], tmp_path / "out",
                                product=False)
    assert [c["id"] for c in out["claims"]] == ["C1", "C2"]
    assert out["loose_quote_matches"] == [
        {"claim": "C1", "source_quote": SQLPARSE_QUOTES[0]["source_quote"]},
        {"claim": "C2", "source_quote": SQLPARSE_QUOTES[1]["source_quote"]}]
    assert out["rejected_claims"] == []


def test_a_printed_dict_parses_when_literal_output_is_on_and_matches_the_recorded_crash():
    crashed = probes.observations_of(TOOLZ_PRINT, 0)
    assert crashed[probes.PROBE_ERROR]["crash"] == "non-json output"
    assert probes.observations_of(TOOLZ_PRINT, 0, literal_output=True) == {"before": [0, 1, 2, 3], "after": [3, 2, 1, 0]}


def test_study_route_passes_literal_output(tmp_path, monkeypatch):
    seen = {}

    def fake_run(*args, **kwargs):
        seen["literal_output"] = kwargs.get("literal_output")
        return {"id": "model-p1", "observations": [], "runs": {"main": [], "pr": []}}

    monkeypatch.setattr(daily_run.freeze, "verify", lambda *a, **k: None)
    monkeypatch.setattr(daily_run.probes, "run_probe", fake_run)
    monkeypatch.setattr(daily_run, "_contree_ready", lambda: False)
    path = tmp_path / "model-p1.py"
    path.write_text("print(" + TOOLZ_PRINT + ")\n")
    venv = tmp_path / "venv-main" / "bin"
    venv.mkdir(parents=True)
    a = SimpleNamespace(runs=1, product_check=False, pr="https://github.com/pytoolz/toolz/pull/654", bench=None,
                        provider=None)
    plan = [{"path": path, "source": "model", "freeze": {"generator": {"kind": "model"}, "sha256": "x",
                                                         "frozen_at": "2026-10-31T00:00:00Z"}}]
    py = {"main": venv / "python", "pr": venv / "python"}
    daily_run.run_probes("pytoolz/toolz", 654, py, tmp_path, tmp_path, a, plan, "2026-10-31T00:00:01Z")
    assert seen["literal_output"] is True
