"""Benchmark scorer: Wilson intervals and exact McNemar match the numbers in the research protocol; joins on ID only."""
import json

import pytest

from evals import score_bench as sb

ANSWERS = "tests/fixtures/bench/answers-synthetic.csv"


@pytest.mark.parametrize("k,n,lo,hi", [(5, 15, 15.2, 58.3), (0, 15, 0.0, 20.4), (10, 15, 41.7, 84.8),
                                       (15, 15, 79.6, 100.0), (1, 4, 4.6, 69.9), (3, 4, 30.1, 95.4)])
def test_wilson_matches_protocol_table(k, n, lo, hi):
    a, b = sb.wilson(k, n)
    assert (round(100 * a, 1), round(100 * b, 1)) == (lo, hi)


def test_acceptance_5_of_15():
    assert sb.pct(sb.wilson(5, 15)[0]) == "15.2%" and sb.pct(sb.wilson(5, 15)[1]) == "58.3%"


@pytest.mark.parametrize("b,c,p", [(6, 0, 0.031), (5, 0, 0.0625), (4, 0, 0.125), (6, 1, 0.125), (8, 2, 0.109),
                                   (0, 6, 0.031), (0, 0, 1.0), (3, 3, 1.0)])
def test_mcnemar_exact_two_sided(b, c, p):
    assert round(sb.mcnemar_exact(b, c), 4 if p == 0.0625 else 3) == p


def test_wilson_and_mcnemar_reject_bad_input():
    with pytest.raises(ValueError):
        sb.wilson(3, 2)
    with pytest.raises(ValueError):
        sb.mcnemar_exact(-1, 2)
    assert sb.wilson(0, 0) == (0.0, 1.0)


def _write(d, name, rid, verdict, baseline=None, **extra):
    rec = {"bench": {"id": rid}, "verdict": verdict, **extra}
    if baseline:
        rec["baseline"] = baseline
    (d / name).write_text(json.dumps(rec))


def test_join_on_id_only(tmp_path):
    # repo/PR fields in a result are ignored: a result claiming another repo still joins by its ID
    _write(tmp_path, "B01-full.json", "B01", "needs_attention", repo="wrong/repo", pr=1)
    _write(tmp_path, "B02-full.json", "B02", "could_not_verify")
    _write(tmp_path, "B03-full.json", "B03", "verified")
    s = sb.score(sb.read_answers(ANSWERS), sb.read_results(tmp_path))
    assert s["regression_recall"]["k"] == 1 and s["regression_recall"]["n"] == 2
    assert s["false_alarm_rate"]["k"] == 0 and s["false_alarm_rate"]["n"] == 1
    assert s["abstention_rate"]["k"] == 1
    assert s["per_id"]["B01"] == {"label": "pos", "verdict": "needs_attention"}


def test_missing_results_are_listed_not_guessed(tmp_path):
    _write(tmp_path, "B01.json", "B01", "needs_attention")
    s = sb.score(sb.read_answers(ANSWERS), sb.read_results(tmp_path))
    assert s["cases_scored"] == 1 and s["missing_results"] == ["B02", "B03"]


def test_baselines_and_paired_comparison(tmp_path, capsys):
    _write(tmp_path, "B01-full.json", "B01", "needs_attention", "full")
    _write(tmp_path, "B02-full.json", "B02", "needs_attention", "full")
    _write(tmp_path, "B01-tests.json", "B01", "verified", "tests")
    _write(tmp_path, "B02-tests.json", "B02", "verified", "tests")
    with pytest.raises(ValueError):
        sb.read_results(tmp_path)          # two results per ID without --baseline
    ans = sb.read_answers(ANSWERS)
    p = sb.compare(ans, sb.read_results(tmp_path, "full"), sb.read_results(tmp_path, "tests"))
    assert p["only_a_flagged"] == ["B01", "B02"] and p["mcnemar_exact_p_two_sided"] == 0.5
    out = tmp_path / "s.json"
    assert sb.main(["--answers", ANSWERS, "--results", str(tmp_path), "--baseline", "full", "--vs", "tests",
                    "--json", str(out)]) == 0
    assert "Regression recall | 2 / 2" in capsys.readouterr().out
    assert json.loads(out.read_text())["vs"]["paired"]["paired_regressions"] == 2


def test_result_files_named_answers_are_ignored(tmp_path):
    _write(tmp_path, "answers-copy.json", "B01", "needs_attention")
    assert sb.read_results(tmp_path) == {}


def test_generic_id_and_label_columns_and_any_case_ids(tmp_path):
    key = tmp_path / "release-answers.csv"
    key.write_text("case,outcome,notes\nR-numpy-2.3,regression,x\nR-pandas-3.0,safe,y\n")
    ans = sb.read_answers(key, id_column="case", label_column="outcome")
    assert ans == {"R-numpy-2.3": "pos", "R-pandas-3.0": "neg"}
    res = tmp_path / "res"
    res.mkdir()
    (res / "a.json").write_text(json.dumps({"case_id": "R-numpy-2.3", "verdict": "needs_attention", "id": "run-1"}))
    (res / "b.json").write_text(json.dumps({"case": {"id": "R-pandas-3.0"}, "verdict": "verified"}))
    s = sb.score(ans, sb.read_results(res))
    assert s["regression_recall"]["k"] == 1 and s["false_alarm_rate"]["k"] == 0
    with pytest.raises(ValueError, match="no column"):
        sb.read_answers(key)                       # default id/label columns are not there
    assert sb.main(["--answers", str(key), "--id-column", "case", "--label-column", "outcome",
                    "--results", str(res)]) == 0


def test_record_run_id_is_not_a_case_id(tmp_path):
    (tmp_path / "r.json").write_text(json.dumps({"id": "B01", "verdict": "needs_attention"}))
    assert sb.read_results(tmp_path) == {}
