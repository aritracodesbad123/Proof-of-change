"""Reviewer reports (reports/generate.py + reports/reviewer.py)."""
import copy
import json
import os
import shutil
from pathlib import Path

import pytest

from reports import reviewer
from reports.generate import generate, load_inputs, main

REPO = Path(__file__).resolve().parent.parent
GOLDEN = REPO / "evals" / "fixtures" / "golden_v1.jsonl"
CLAIMS = REPO / "evals" / "fixtures" / "claims"
REV2 = REPO / "evals" / "fixtures" / "record_rev2_example.json"
RESEARCH = Path(os.environ.get("BR_RESEARCH_DIR", "/workspace/blast-radius-research"))  # box-only; tests skip without it
HAVE_ARTIFACTS = (RESEARCH / "research" / "runs" / "golden-sklearn160rc1-imblearn0124" / "pytest-new-1.log").exists()
EXPECTED = {  # Jonathan's samples (blast-radius-research/reports/samples) and Aritra's acceptance list
    "golden-sklearn160rc1-imblearn0124": ("NEEDS ATTENTION", "Reject"),
    "golden-pandas300rc0-upsetplot090": ("NEEDS ATTENTION", "Reject"),
    "golden-clean-sklearn151to152-imblearn0124": ("VERIFIED", "Approve"),
}
SECTIONS = ["Summary in plain English", "Claims vs reality", "What changed in behavior", "What went right",
            "What went wrong and how to fix it", "Trust checks", "Evals and guardrails (Nathan)", "Reviewer checklist",
            "Rerun command", "Evidence links", "Appendix", "Glossary"]


def _golden(tmp_path, runs_root=None, formats=("md", "html")):
    return generate([str(GOLDEN)], tmp_path, runs_root, CLAIMS, formats, require_v1=True)


def test_golden_verdicts_without_artifacts(tmp_path):
    sums = {s["id"]: s for s in _golden(tmp_path)}
    assert {k: (v["verdict"], v["action"]) for k, v in sums.items()} == EXPECTED
    assert all(s["evals"] == "APPROVE" for s in sums.values())
    for rid in EXPECTED:
        md = (tmp_path / rid / "REPORT.md").read_text()
        pos = [md.index("## " + s) for s in SECTIONS]
        assert pos == sorted(pos), rid  # sections in the agreed order
        assert md.index("Recommended action:") < md.index("## Summary in plain English")
        assert "**Confidence:**" in md
        summary = md.split("## Summary in plain English")[1].split("##")[0]
        assert summary.count("\n- ") == 3  # 3-line plain-English summary
        assert (tmp_path / rid / "REPORT.html").read_text().startswith("<!doctype html>")


@pytest.mark.skipif(not HAVE_ARTIFACTS, reason="run artifacts of the golden records are only on the box")
def test_golden_reports_with_artifacts_cite_every_claim(tmp_path):
    sums = {s["id"]: s for s in _golden(tmp_path, RESEARCH)}
    assert {k: (v["verdict"], v["action"], v["confidence"]) for k, v in sums.items()} == \
        {k: (*v, "High") for k, v in EXPECTED.items()}
    for rid in ("golden-sklearn160rc1-imblearn0124", "golden-pandas300rc0-upsetplot090"):
        s = sums[rid]
        assert s["citations"] == "pass" and s["claims"]
        assert all(c["citation"] and c["citation"]["file"].startswith("pytest-new-") for c in s["claims"])
    sk = sums["golden-sklearn160rc1-imblearn0124"]["claims"]
    assert [c["status"] for c in sk] == ["not testable", "unmentioned change"]
    pd = sums["golden-pandas300rc0-upsetplot090"]["claims"]
    assert len([c for c in pd if c["status"] == "unmentioned change"]) == 5  # 5 break groups, as in Jonathan's sample
    md = (tmp_path / "golden-pandas300rc0-upsetplot090" / "REPORT.md").read_text()
    assert "67 real break(s) in 5 group(s)" in md and "consistent" in md
    clean = (tmp_path / "golden-clean-sklearn151to152-imblearn0124" / "REPORT.md").read_text()
    assert "pytest summary, new side run 1" in clean and "2238 passed" in clean


def test_daily_summary_lists_needs_attention_first(tmp_path):
    _golden(tmp_path)
    md = (tmp_path / "SUMMARY.md").read_text()
    first = md.split("## Needs attention first")[1].split("## All reports")[0]
    assert "golden-clean" not in first and first.count("NEEDS ATTENTION / Reject") == 2
    table = md.split("## All reports")[1]
    assert table.index("NEEDS ATTENTION") < table.index("VERIFIED")
    assert "golden-sklearn160rc1-imblearn0124/REPORT.pdf" in md


def _tmp_run(tmp_path, rec, log_lines):
    rd = tmp_path / "runs" / rec["id"]
    rd.mkdir(parents=True)
    (rd / "pytest-new-1.log").write_text("\n".join(log_lines) + "\n")
    (rd / "class-real_break.txt").write_text("")
    (rd / "class-import_failure.txt").write_text("\n".join(f"mod{i}.tests" for i in range(46)) + "\n")
    (rd / "class-lost_tests.txt").write_text("")
    r = copy.deepcopy(rec)
    r["logs"] = f"runs/{rec['id']}"
    return r


def test_citations_are_verified_against_the_log(tmp_path, g_sklearn):
    good = ["collecting ...", "E   ImportError: cannot import name '_safe_tags' from 'sklearn.utils._tags' (/x/_tags.py)",
            "525 errors in 14.44s"]
    r = _tmp_run(tmp_path, g_sklearn, good)
    claims = json.loads((CLAIMS / "golden-sklearn160rc1-imblearn0124.claims.json").read_text())
    rd = reviewer.resolve_run_dir(r, tmp_path)
    logs = reviewer.LogIndex(rd)
    imp = reviewer.import_group(r, rd, {})
    rows = reviewer.eval_claims(claims, [], imp, logs)
    assert [(x["citation"]["file"], x["citation"]["line"]) for x in rows] == [("pytest-new-1.log", 2)] * 2
    assert reviewer.verify_citations(rows, rd).status == "pass"
    rows[0]["citation"] = {"file": "pytest-new-1.log", "line": 1, "quote": "_safe_tags"}  # wrong line
    assert reviewer.verify_citations(rows, rd).status == "fail"
    rows[0]["citation"] = None
    assert reviewer.verify_citations(rows, rd).status == "fail"


def test_uncited_claim_lowers_confidence(tmp_path, g_sklearn):
    r = _tmp_run(tmp_path, g_sklearn, ["nothing relevant here", "525 errors in 14.44s"])
    out = generate([], tmp_path / "o")  # empty batch is fine
    assert out == []
    s = reviewer.render_record(r, str(tmp_path / "rep"), tmp_path, None, CLAIMS / "golden-sklearn160rc1-imblearn0124.claims.json",
                               formats=("md",))
    assert s["citations"] == "fail" and s["confidence"] != "High"
    assert (s["verdict"], s["action"]) == ("NEEDS ATTENTION", "Reject")


def test_eval_failure_means_could_not_verify(tmp_path, g_clean):
    r = copy.deepcopy(g_clean)
    r["thread_env"]["OMP_NUM_THREADS"] = "8"  # single_thread eval fails (and the schema enum)
    s = reviewer.render_record(r, str(tmp_path), formats=("md",), require_v1=True)
    assert (s["verdict"], s["action"], s["confidence"]) == ("COULD NOT VERIFY", "Re-run", "Low")
    md = (tmp_path / "REPORT.md").read_text()
    assert "eval check(s) failed" in md and "Eval FAIL: single_thread" in md


def test_not_accepted_means_could_not_verify(tmp_path, g_pandas):
    r = copy.deepcopy(g_pandas)
    r["accepted"], r["classification"] = False, None
    r["gates"]["runs_complete"]["pass"] = False
    s = reviewer.render_record(r, str(tmp_path), formats=("md",))
    assert (s["verdict"], s["action"]) == ("COULD NOT VERIFY", "Re-run")


def test_flaky_means_approve_with_notes(tmp_path, g_clean):
    r = copy.deepcopy(g_clean)
    r["classification"]["flaky"] = 2
    r["dependent"] = "imbalanced-learn-fork"  # not the golden pair, whose golden case requires flaky == 0
    s = reviewer.render_record(r, str(tmp_path), formats=("md",))
    assert (s["verdict"], s["action"]) == ("VERIFIED", "Approve with notes")


def test_rev2_fields_used(tmp_path):
    s = generate([str(REV2)], tmp_path, RESEARCH if HAVE_ARTIFACTS else None, None, ("md",), require_v1=True)[0]
    md = (tmp_path / s["id"] / "REPORT.md").read_text()
    assert md.startswith("# Reviewer report: scikit-learn/scikit-learn#29677: API Revamp estimator tags")
    assert "Scope: this run compares two released versions" not in md  # it names a PR
    assert "**Decision recorded:** reject by example reviewer on 2026-10-10" in md
    assert "re-run with harness 1.0 on 2026-10-10" in md
    assert [c["status"] for c in s["claims"]][:2] == ["not testable", "false"]  # C2 no_breaks is contradicted
    assert "0bfebf4235f37c09625e07d9fb0060210b3e0fdd" in md


def test_rerun_command_uses_wrapper():
    args = {"upstream": "pandas", "old": "2.3.3", "new": "3.0.0rc0", "dependent": "UpSetPlot", "runs": 3, "workers": "4",
            "extra_pkgs": "numpy==2.3.5", "python": "3.13"}
    cmd = reviewer.repro_command(args, {"id": "x"})
    assert "python -m harness.run" in cmd and "--runs" not in cmd and "--workers" not in cmd
    assert "--extra-pkgs numpy==2.3.5" in cmd and cmd.endswith("--id x-rerun")


def test_load_inputs_kinds(tmp_path, g_pandas):
    rec = tmp_path / "record.json"
    rec.write_text(json.dumps(g_pandas))
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"records": [{"record": g_pandas}]}))
    got = load_inputs([str(GOLDEN), str(rec), str(ev)])
    assert [r["id"] for r, _ in got].count("golden-pandas300rc0-upsetplot090") == 3
    assert got[3][1] == rec


def test_jonathans_command_still_works(tmp_path):
    import runpy
    import sys
    argv = sys.argv
    sys.argv = ["render_report.py", str(REV2), "--out", str(tmp_path), "--formats", "md", "--golden-dir", "ignored"]
    try:
        with pytest.raises(SystemExit) as e:
            runpy.run_path(str(REPO / "harness" / "report" / "render_report.py"), run_name="__main__")
        assert e.value.code == 0
    finally:
        sys.argv = argv
    assert (tmp_path / "SUMMARY.md").exists()


@pytest.mark.skipif(not reviewer.find_chrome(), reason="no Chrome/Chromium for PDF")
def test_pdf_rendered(tmp_path):
    shutil.copy(REV2, tmp_path / "rec.json")
    assert main([str(tmp_path / "rec.json"), "--out", str(tmp_path / "o"), "--formats", "md,html,pdf"]) == 0
    for p in (tmp_path / "o" / "example-rev2-sklearn160rc1-imblearn0124" / "REPORT.pdf", tmp_path / "o" / "SUMMARY.pdf"):
        assert p.read_bytes()[:5] == b"%PDF-"


def test_no_breaks_claim_without_artifacts_uses_record_counts(tmp_path):
    """CI has no run artifacts: a 'no breaks' claim must still be false when the record shows import failures."""
    s = generate([str(REV2)], tmp_path, None, None, ("md",), require_v1=True)[0]
    c2 = [c for c in s["claims"] if c["id"] == "C2"][0]
    assert c2["status"] == "false"
