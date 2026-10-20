"""Verdict changes: a missing module, old-bug sentences, markdown quotes, import adequacy, extra cases, docstrings."""
from ops import daily_run
from poc import behaviour_claims, model_probes, probe_adequacy, probes
from reports import pr_report

IMP = "E   ModuleNotFoundError: No module named 'scipy'"
IMP2 = "E   ImportError: cannot import name 'x' from 'pkg.mod'"
ASSERT = "E   AssertionError: boom"


def _tri(main, pr):
    return {"main": [main] * 3, "pr": [pr] * 3}


def _same_cmp():
    return daily_run.compare_sides(_tri({"t::ok": ("passed", "")}, {"t::ok": ("passed", "")}))


def _coverage():
    return {"status": "measured", "changed_lines_total": 4, "changed_lines_covered": 2, "adequacy": "adequate"}


def test_every_test_failing_on_a_missing_module_is_could_not_verify():
    both = {"t::a": ("failed", IMP), "t::b": ("error", IMP2)}
    cmp = daily_run.compare_sides(_tri(both, both))
    assert cmp["missing_dependency_all"] == ["pkg", "scipy"]
    verdict, reason, _ = daily_run.verdict_for(cmp, None)
    assert verdict == "could_not_verify"
    assert "missing dependency" in reason and "scipy" in reason and "verified" not in verdict


def test_assertion_errors_and_a_mix_stay_on_the_old_rule():
    both = {"t::a": ("failed", ASSERT)}
    cmp = daily_run.compare_sides(_tri(both, both))
    assert "missing_dependency_all" not in cmp
    assert daily_run.verdict_for(cmp, None)[0] == "verified"
    mixed = {"t::a": ("failed", IMP), "t::b": ("passed", "")}
    assert daily_run.verdict_for(daily_run.compare_sides(_tri(mixed, mixed)), None)[0] == "verified"


def test_a_sentence_about_the_old_bug_is_not_an_unchanged_claim():
    assert behaviour_claims.find("t", "Previously the results were left unchanged.") == []
    assert behaviour_claims.find("t", "The old behaviour left results unchanged.") == []
    assert behaviour_claims.find("t", "This fixes a bug where results are unchanged.") == []
    assert behaviour_claims.find("t", "Results were incorrectly left unchanged.") == []
    kept = behaviour_claims.find("t", "Fixes the dtype. Results are unchanged.")
    assert [c["quote"] for c in kept] == ["Results are unchanged."]
    assert behaviour_claims.find("t", "This bugfix keeps results unchanged.")


def test_markdown_is_stripped_before_a_quote_is_matched():
    raw = {"claims": [{"id": "c", "source_quote": "results stay the same", "expect": "same"}]}
    body = "See **results stay the same** in [`the note`](https://example.com/note)."
    kept, rejected = model_probes.grounded_claims(raw, "Title", body)
    assert [c["id"] for c in kept] == ["c"] and rejected == []
    quoted = {"claims": [{"id": "c", "source_quote": "`results stay the same`", "expect": "same"}]}
    kept, rejected = model_probes.grounded_claims(quoted, "Title", "results stay the same")
    assert kept and not rejected


def test_a_probe_that_cannot_import_on_either_side_is_not_adequate():
    item = {"id": "p", "source": "model", "target": "pkg.fn", "claims": [
                {"id": "c", "text": "same", "covers": ["pkg.fn.*"], "expect": "same"}],
            "observations": [{"name": "pkg.fn.out", "state": "differs", "label": "unmentioned", "claim": None,
                              "main": {"raises": "ModuleNotFoundError", "msg": "missing"},
                              "pr": {"raises": "ImportError"}}],
            "probe_changed_line_coverage": _coverage()}
    got = probes.classify_item(item)
    assert got["status"] == "uninformative"
    assert "cannot import its target" in got["uninformative_reason"]
    assert got["probe_changed_line_coverage"]["adequacy"] == "not_adequate"
    assert got["probe_changed_line_coverage"]["changed_lines_covered"] == 0
    verdict, reason, _ = daily_run.verdict_for(_same_cmp(), None, None, None, {"items": [item]}, baseline="tests+probes")
    assert verdict == "verified"
    assert "cannot import" in reason
    one = dict(item, source="library", observations=[
        {"name": "pkg.fn.out", "state": "differs", "label": "unmentioned", "claim": None,
         "main": {"raises": "ImportError"}, "pr": 5}])
    kept, _notes = probe_adequacy.deciding_items([one])
    assert kept[0]["observations"]
    diff_verdict = daily_run.verdict_for(_same_cmp(), None, None, None, {"items": [one]}, baseline="tests+probes")[0]
    assert diff_verdict == "needs_attention"


def test_extra_model_cases_do_not_count_against_the_claim():
    item = {"id": "m1", "source": "model", "status": "ran", "target": "pkg.fn",
            "claims": [{"id": "c1", "text": "stays", "covers": ["pkg.fn.claimed"], "expect": "same"}],
            "observations": [
                {"name": "pkg.fn.claimed", "state": "same", "label": "proven", "claim": "c1", "main": 1, "pr": 1},
                {"name": "pkg.fn.extra", "state": "differs", "label": "unmentioned", "claim": None, "main": 1, "pr": 2},
            ],
            "probe_changed_line_coverage": _coverage()}
    verdict, reason, _ = daily_run.verdict_for(_same_cmp(), None, None, None, {"items": [item]}, baseline="tests+probes")
    assert verdict == "verified"
    assert "extra case" in reason and "not counted" in reason
    rows = pr_report.probe_claim_rows({"baseline": "tests+probes", "probes": {"items": [item]}})
    assert all(r["text"] != "Change not in the PR description" for r in rows)
    diff = dict(item, id="d1", source="diff", claims=[])
    diff_verdict = daily_run.verdict_for(_same_cmp(), None, None, None, {"items": [diff]}, baseline="tests+diff")[0]
    assert diff_verdict == "needs_attention"


def test_docstring_or_comment_only_is_no_code_change(tmp_path):
    rel = "pkg/m.py"
    main, pr = tmp_path / "main", tmp_path / "pr"
    for root, text in ((main, "def load(x):\n    return x\n"), (pr, "def load(x):\n    return x  # kept\n")):
        path = root / rel
        path.parent.mkdir(parents=True)
        path.write_text(text)
    files = {"all": [rel], "package_py": [rel], "compiled": [], "other": []}
    assert daily_run.change_is_docstring_only(files, main, pr)
    verdict, reason, _ = daily_run.verdict_for(_same_cmp(), None, None, files, docstring_only=True, baseline="tests")
    assert verdict == "no_code_change"
    assert "only docstrings or comments changed" in reason
    rec = {"docstring_only": True, "files": files, "baseline": "tests",
           "behaviour_claims": [{"source": "PR description", "quote": "Results are unchanged.", "pattern": "unchanged"}]}
    daily_run._store_verdict(rec, _same_cmp(), None, None)
    assert rec["verdict"] == "no_code_change"
    assert rec["no_code_change"] is True and rec["no_code_change_reason"] == "docstring_only"
    assert rec["behaviour_claims"][0]["status"] == "holds by construction"
    reg = daily_run.compare_sides(_tri({"t::ok": ("passed", "")}, {"t::ok": ("failed", ASSERT)}))
    assert daily_run.verdict_for(reg, None, None, files, docstring_only=True)[0] == "needs_attention"


def test_docstring_only_report_does_not_call_it_a_type_stub(monkeypatch):
    monkeypatch.setattr(pr_report.rv, "replay_failure", lambda *a, **k: None)
    decision = pr_report.decide({"verdict": "no_code_change", "no_code_change_reason": "docstring_only",
                                 "reason": "no code change: only docstrings or comments changed"}, [])
    assert decision["verdict"] == "NO CODE CHANGE"
    assert "docstrings or comments" in decision["conf_why"]
    assert "type stub" not in decision["conf_why"]
