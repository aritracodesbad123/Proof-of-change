"""The library label follows the written rule and does not change the pair list."""
import json
from pathlib import Path

from evals.label_study_pairs import counts, judge, label_pairs, link_matches, main

ROOT = Path(__file__).resolve().parent.parent
PAIRS = ROOT / "evals" / "study_pairs" / "main-study-pairs.json"
RULE = ROOT / "evals" / "study_pairs" / "library_label_rule.md"


def _body(home=None, urls=None):
    return json.dumps({"info": {"home_page": home, "project_urls": urls}}).encode()


def test_link_match_ignores_case_git_and_slash_and_rejects_a_longer_name():
    assert link_matches("https://GitHub.com/Acme/Widget.git", "Acme", "Widget")
    assert link_matches("https://github.com/acme/widget/", "Acme", "Widget")
    assert link_matches("https://github.com/acme/widget/tree/main", "acme", "widget")
    assert link_matches("https://github.com/acme/widget?tab=readme", "acme", "widget")
    assert not link_matches("https://github.com/acme/widget-extra", "acme", "widget")
    assert not link_matches("https://github.com/acme/widgetry", "acme", "widget")
    assert not link_matches("https://example.com/acme/widget", "acme", "widget")


def test_status_and_links_decide_the_label():
    assert judge(200, _body(home="https://github.com/acme/widget"), "acme", "widget") == "library"
    assert judge(200, _body(urls={"Source": "https://github.com/acme/widget.git"}), "acme", "widget") == "library"
    assert judge(200, _body(urls={"Source": "https://example.com"}), "acme", "widget") == "non_library"
    assert judge(200, _body(home="https://github.com/other/widget"), "acme", "widget") == "non_library"
    assert judge(404, b"missing", "acme", "widget") == "non_library"
    assert judge(200, b"not-json", "acme", "widget") is None
    assert judge(503, b"", "acme", "widget") is None
    assert judge(429, b"", "acme", "widget") is None


def test_unreachable_after_three_retries_is_unknown():
    calls = {"n": 0}

    def fetch(_name):
        calls["n"] += 1
        raise TimeoutError("down")

    labelled = label_pairs([{"repo": "acme/widget", "agent_pr": 1, "human_pr": 2}], fetch, sleep=lambda _s: None)
    assert calls["n"] == 4
    assert labelled == [{"repo": "acme/widget", "agent_pr": 1, "human_pr": 2, "label": "unknown"}]


def test_a_later_success_is_kept_and_each_repository_is_looked_up_once():
    calls = []

    def fetch(name):
        calls.append(name)
        if name == "widget" and calls.count("widget") < 3:
            return 503, b""
        if name == "widget":
            return 200, _body(home="https://github.com/acme/widget/")
        return 404, b"no"

    pairs = [{"repo": "acme/widget", "agent_pr": 2, "human_pr": 9},
             {"repo": "acme/other", "agent_pr": 3, "human_pr": 4},
             {"repo": "acme/widget", "agent_pr": 5, "human_pr": 6},
             {"repo": "not a repo", "agent_pr": 7, "human_pr": 8}]
    labelled = label_pairs(pairs, fetch, sleep=lambda _s: None)
    assert calls == ["widget", "widget", "widget", "other"]
    assert [item["label"] for item in labelled] == ["library", "non_library", "library", "non_library"]
    assert counts(labelled) == {"library": 2, "non_library": 2, "unknown": 0}


def test_command_writes_labels_and_leaves_the_pair_list_alone(tmp_path):
    before = PAIRS.read_bytes()
    out = tmp_path / "pair-labels.json"

    def fetch(name):
        return 200, _body(home=f"https://github.com/acme/{name}")

    # The command uses the real reader. This test checks the writer through main only when the
    # rule file is present, with the network replaced for one tiny list.
    src = tmp_path / "pairs.json"
    src.write_text(json.dumps([{"repo": "acme/widget", "agent_pr": 1, "human_pr": 2}]))
    import evals.label_study_pairs as mod
    original = mod.default_fetch
    mod.default_fetch = fetch
    try:
        assert main(["--pairs", str(src), "--rule", str(RULE), "--out", str(out)]) == 0
    finally:
        mod.default_fetch = original
    assert json.loads(out.read_text()) == [{"repo": "acme/widget", "agent_pr": 1, "human_pr": 2, "label": "library"}]
    assert PAIRS.read_bytes() == before
    missing = tmp_path / "missing-rule.md"
    assert main(["--pairs", str(src), "--rule", str(missing), "--out", str(tmp_path / "no.json")]) == 2
