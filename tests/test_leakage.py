"""Answer-key firewall (poc/leakage.py). Uses a synthetic answer key, never the real one."""
import json
import re

import pytest

from poc import leakage
from poc.leakage import LeakageError, check_bundle

ANSWERS = "tests/fixtures/bench/answers-synthetic.csv"


def bundle(**text):
    return {"pr": "example-org/widgets#4100", "text": {"title": "Use handle settings when picking a pool", **text}}


def test_clean_bundle_passes():
    r = check_bundle(bundle(body="This PR uses the handle settings when choosing a pool. Fixes #4000."), ANSWERS)
    assert r["ok"]


def test_planted_answer_phrase_is_refused():
    planted = "Note: subclasses overriding it fail with 'Unsupported handle scheme zebra' after this."
    with pytest.raises(LeakageError, match="phrase"):
        check_bundle(bundle(body=planted), ANSWERS)


def test_planted_phrase_with_different_case_and_punctuation_is_refused():
    with pytest.raises(LeakageError, match="phrase"):
        check_bundle(bundle(body="SORTING a widget-table, with duplicate keys now drops the trailing rows!"), ANSWERS)


@pytest.mark.parametrize("planted", [
    "see https://github.com/example-org/widgets/issues/4242",
    "see http://www.GitHub.com/example-org/widgets/issues/4242/",
    "see example-org/widgets#4242",
    "see widgets#4242",
    "see #4242",                      # same repository as the PR
    "see GH-5150",
    "see issues/5150",
    "downstream-org/gadgets#77",
])
def test_planted_url_or_issue_number_is_refused(planted):
    with pytest.raises(LeakageError, match="URL|reference"):
        check_bundle(bundle(body=planted), ANSWERS)


def test_bare_number_of_another_repository_is_not_a_reference():
    # '#77' is an issue of downstream-org/gadgets, not of the PR's repository
    assert check_bundle(bundle(body="Follow-up to #77."), ANSWERS)["ok"]


def test_refusal_does_not_echo_the_answer_text():
    with pytest.raises(LeakageError) as e:
        check_bundle(bundle(body="fail with 'Unsupported handle scheme zebra' https://github.com/example-org/widgets/issues/4242"),
                     ANSWERS)
    msg = str(e.value)
    assert "zebra" not in msg and "4242" not in msg and re.search(r"sha [0-9a-f]{10}", msg)


def test_planted_answer_in_a_file_is_refused():
    b = bundle() | {"files": {"src/widgets/adapters.py": "# regression: widgets#4242\nx = 1\n"}}
    with pytest.raises(LeakageError, match=r"files\[src/widgets/adapters.py\]"):
        check_bundle(b, ANSWERS)


def test_pr_head_only_file_is_refused():
    b = bundle() | {"files": {"src/widgets/new_module.py": "x = 1\n", "src/widgets/adapters.py": "y = 2\n"}}
    with pytest.raises(LeakageError, match="exists only on the PR side") as e:
        check_bundle(b, ANSWERS, base_files={"src/widgets/adapters.py"},
                     pr_files={"src/widgets/adapters.py", "src/widgets/new_module.py"})
    assert "adapters.py" not in str(e.value)


def test_base_root_checks_files_exist_and_exempts_identical_files_from_phrases(tmp_path):
    lib_text = "def sort(t):\n    # sorting a widget table with duplicate keys now drops the trailing rows\n    pass\n"
    (tmp_path / "widgets").mkdir()
    (tmp_path / "widgets" / "table.py").write_text(lib_text)
    ok = check_bundle(bundle() | {"files": {"widgets/table.py": lib_text}}, ANSWERS, base_root=tmp_path)
    assert ok["checked"]["phrase_exempt_base_identical"] == ["widgets/table.py"]
    with pytest.raises(LeakageError, match="phrase"):     # same text, but not what the base tree has
        check_bundle(bundle() | {"files": {"widgets/table.py": lib_text + "\n"}}, ANSWERS, base_root=tmp_path)
    with pytest.raises(LeakageError, match="not in the base tree"):
        check_bundle(bundle() | {"files": {"widgets/other.py": "x = 1\n"}}, ANSWERS, base_root=tmp_path)
    with pytest.raises(LeakageError, match="repo-relative"):
        check_bundle(bundle() | {"files": {"../escape.py": "x = 1\n"}}, ANSWERS)


def test_own_pr_url_is_allowed():
    assert check_bundle(bundle(body="https://github.com/example-org/widgets/pull/4100 and #4100"), ANSWERS)["ok"]


def test_fingerprints_hold_no_plain_text_and_round_trip(tmp_path):
    fp = leakage.fingerprints(ANSWERS)
    dumped = json.dumps(fp.to_json())
    assert "zebra" not in dumped and "4242" not in dumped and "example-org" not in dumped
    fp2 = leakage.Fingerprints.from_json(json.loads(dumped))
    with pytest.raises(LeakageError):
        check_bundle(bundle(body="widgets#4242"), fp2)
    out = tmp_path / "fp.json"
    assert leakage.main(["fingerprint", ANSWERS, "--out", str(out)]) == 0
    b = tmp_path / "b.json"
    b.write_text(json.dumps(bundle(body="drops the trailing rows silently when sorting a widget table with duplicate keys")))
    assert leakage.main(["check", str(b), "--fingerprints", str(out)]) == 1
    b.write_text(json.dumps(bundle(body="faster sort")))
    assert leakage.main(["check", str(b), "--answers", ANSWERS]) == 0


def test_generic_phrases_are_not_refused():
    # common words shared with the answer key ('the', 'with', 'now') do not form a 5-word phrase with 3 content words
    assert check_bundle(bundle(body="Now the pool is picked with the settings of the handle."), ANSWERS)["ok"]
