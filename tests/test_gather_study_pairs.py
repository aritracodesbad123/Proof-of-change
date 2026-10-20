"""A missing patch is skipped. The ordered list is the same every time for one seed."""
import hashlib
import json
import random
from pathlib import Path

import pytest

from evals.gather_study_pairs import (
    AnswerKeyRefused,
    StudyPairError,
    load_rules,
    main,
    match_candidates,
    read_candidates,
    write_list,
)

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "evals" / "study_pair_rules.json"

DIFF_A = """diff --git a/src/a.py b/src/a.py
--- a/src/a.py
+++ b/src/a.py
@@ -1 +1 @@
-old
+new
"""
DIFF_B = """diff --git a/src/b.py b/src/b.py
--- a/src/b.py
+++ b/src/b.py
@@ -1 +1 @@
-old
+new
"""


def _rules(**over):
    data = json.loads(RULES_PATH.read_text())
    data.update(over)
    return data


def _write_csv(path: Path, rows: list[dict], columns=None) -> None:
    columns = columns or ["repo", "agent_pr", "human_pr", "agent_patch", "human_patch"]
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(str(row.get(c, "")) for c in columns))
    path.write_text("\n".join(lines) + "\n")


def _pair(tmp_path: Path, n: int, *, repo="acme/lib", human=None, agent_diff=DIFF_A, human_diff=DIFF_A,
          agent_text=None, human_text=None, write_agent=True, write_human=True) -> dict:
    agent_name = f"agent-{n}.diff"
    human_name = f"human-{n}.diff"
    if write_agent:
        (tmp_path / agent_name).write_text(DIFF_A if agent_text is None else agent_text)
    if write_human:
        text = human_diff if human_text is None else human_text
        (tmp_path / human_name).write_text(text)
    return {"repo": repo, "agent_pr": str(n), "human_pr": str(human if human is not None else n + 100),
            "agent_patch": agent_name, "human_patch": human_name}


def test_committed_rules_keep_the_stated_seed_and_refuse_a_rebuilt_patch(tmp_path):
    rules = load_rules(RULES_PATH)
    assert rules["seed"] == 20261020
    assert rules["cap"] == 175
    assert rules["reconstruct_missing_patch"] is False
    rules["reconstruct_missing_patch"] = True
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(rules))
    with pytest.raises(StudyPairError, match="reconstruct_missing_patch"):
        load_rules(path)


def test_missing_patch_is_skipped_and_not_created(tmp_path):
    good = _pair(tmp_path, 1)
    missing_human = _pair(tmp_path, 2, write_human=False)
    missing_agent = _pair(tmp_path, 3, write_agent=False)
    csv_path = tmp_path / "candidates.csv"
    _write_csv(csv_path, [missing_human, good, missing_agent])
    pairs, excluded = match_candidates(read_candidates(csv_path), _rules())
    assert pairs == [{"repo": "acme/lib", "agent_pr": 1, "human_pr": 101}]
    reasons = {(e["agent_pr"], e["reason"], e.get("side")) for e in excluded}
    assert reasons == {("2", "missing_patch", "human"), ("3", "missing_patch", "agent")}
    assert not (tmp_path / "human-2.diff").exists()
    assert not (tmp_path / "agent-3.diff").exists()


def test_empty_and_non_diff_patches_are_skipped(tmp_path):
    empty = _pair(tmp_path, 1, human_text="   \n")
    prose = _pair(tmp_path, 2, human_text="this is not a diff\n")
    good = _pair(tmp_path, 3)
    csv_path = tmp_path / "candidates.csv"
    _write_csv(csv_path, [empty, prose, good])
    pairs, excluded = match_candidates(read_candidates(csv_path), _rules())
    assert [p["agent_pr"] for p in pairs] == [3]
    assert {(e["agent_pr"], e["reason"], e["side"]) for e in excluded} == {
        ("1", "empty_patch", "human"), ("2", "not_a_diff", "human")}


def test_repo_pr_and_file_checks_exclude_without_adding_pairs(tmp_path):
    bad_repo = _pair(tmp_path, 1, repo="not a repo")
    same = _pair(tmp_path, 2, human=2)
    first = _pair(tmp_path, 4)
    duplicate = dict(first)
    no_share = _pair(tmp_path, 5, human_diff=DIFF_B)
    csv_path = tmp_path / "candidates.csv"
    _write_csv(csv_path, [bad_repo, same, first, duplicate, no_share])
    pairs, excluded = match_candidates(read_candidates(csv_path), _rules())
    assert pairs == [{"repo": "acme/lib", "agent_pr": 4, "human_pr": 104}]
    assert [(e["repo"], e["agent_pr"], e["reason"]) for e in excluded] == [
        ("acme/lib", "2", "same_pull_request"),
        ("acme/lib", "4", "duplicate"),
        ("acme/lib", "5", "no_shared_file"),
        ("not a repo", "1", "different_repo"),
    ]


def test_fewer_than_the_cap_stays_short_and_overflow_is_logged(tmp_path):
    rows = [_pair(tmp_path, n) for n in range(1, 5)]
    csv_path = tmp_path / "candidates.csv"
    _write_csv(csv_path, rows)
    short, excluded = match_candidates(read_candidates(csv_path), _rules())
    assert len(short) == 4
    assert excluded == []
    capped, overflow = match_candidates(read_candidates(csv_path), _rules(cap=2))
    assert len(capped) == 2
    assert {e["reason"] for e in overflow} == {"over_cap"}
    assert len(overflow) == 2


def test_order_is_a_fixed_shuffle_of_the_sorted_pairs(tmp_path):
    rows = [_pair(tmp_path, n, repo=f"acme/lib{n}") for n in (3, 1, 2)]
    csv_path = tmp_path / "candidates.csv"
    _write_csv(csv_path, rows)
    expected = [{"repo": f"acme/lib{n}", "agent_pr": n, "human_pr": n + 100} for n in (1, 2, 3)]
    random.Random(20261020).shuffle(expected)
    first, _ = match_candidates(read_candidates(csv_path), _rules())
    second, _ = match_candidates(read_candidates(csv_path), _rules())
    assert first == second == expected
    other, _ = match_candidates(read_candidates(csv_path), _rules(seed=1))
    assert other != first


def test_verdict_and_label_columns_are_refused_before_the_values_are_used(tmp_path):
    secret = "VERDICT-SECRET-do-not-leak"
    path = tmp_path / "candidates.csv"
    _write_csv(path, [{"repo": "acme/lib", "agent_pr": "1", "human_pr": "2", "agent_patch": "a.diff",
                       "human_patch": "h.diff", "label": secret, "expected_verdict": secret}],
               columns=["repo", "agent_pr", "human_pr", "agent_patch", "human_patch", "label", "expected_verdict"])
    with pytest.raises(AnswerKeyRefused) as caught:
        read_candidates(path)
    message = str(caught.value)
    assert "label" in message and "expected_verdict" in message
    assert secret not in message
    assert not (tmp_path / "a.diff").exists()


def test_an_answer_key_filename_is_refused(tmp_path):
    secret = "ANSWER-SECRET-do-not-leak"
    path = tmp_path / "pilot-answers.csv"
    path.write_text(f"repo,agent_pr,human_pr,agent_patch,human_patch\nacme/lib,1,2,a.diff,h.diff\n{secret}\n")
    with pytest.raises(AnswerKeyRefused) as caught:
        read_candidates(path)
    assert secret not in str(caught.value)


def test_manifest_hashes_the_list_and_the_rules(tmp_path):
    row = _pair(tmp_path, 7)
    csv_path = tmp_path / "candidates.csv"
    _write_csv(csv_path, [row])
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(RULES_PATH.read_text())
    out = tmp_path / "list.json"
    manifest_path = tmp_path / "manifest.json"
    rules = load_rules(rules_path)
    pairs, excluded = match_candidates(read_candidates(csv_path), rules)
    manifest = write_list(pairs, excluded, rules_path, out, manifest_path, rules)
    again = write_list(pairs, excluded, rules_path, tmp_path / "list2.json", tmp_path / "manifest2.json", rules)
    assert manifest["matched"] == 1
    assert manifest["seed"] == 20261020
    assert manifest["exclusion_counts"] == {}
    assert manifest["list_sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert manifest["rules_sha256"] == hashlib.sha256(rules_path.read_bytes()).hexdigest()
    assert again["list_sha256"] == manifest["list_sha256"]
    assert json.loads(manifest_path.read_text())["exclusions"] == []
    assert main(["--candidates", str(csv_path), "--rules", str(rules_path),
                 "--out", str(tmp_path / "cli.json"), "--manifest", str(tmp_path / "cli-manifest.json")]) == 0
    assert main(["--candidates", str(tmp_path / "pilot-answers.csv"), "--rules", str(rules_path),
                 "--out", str(tmp_path / "no.json"), "--manifest", str(tmp_path / "no-manifest.json")]) == 2
