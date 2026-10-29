"""Edited existing patterns get probes on inputs just past the old match boundary (poc/boundary_probes.py).

Fixtures: tests/fixtures/boundary holds two saved PR diffs, copied unchanged: one edits an existing tag pattern
(it must fire), one adds a brand-new token pattern (it must stay silent). It also holds one saved probe entry
whose expect-same claim and probe on a tag followed by a space show the lost match. Nothing here runs a model,
a search or a sandbox."""
import json
from pathlib import Path

import pytest

from poc import boundary_probes as bp
from poc import model_probes, model_provider, probes
from poc.verdict import COLOUR, FindingLabel

FX = Path(__file__).parent / "fixtures" / "boundary"
EDITED = (FX / "rich-4147.diff").read_text()
ADDED = (FX / "sqlparse-928.diff").read_text()
SAVED = json.loads((FX / "rich-4147-live140-c2.json").read_text())
OLD_TAG = r"(?P<tag_start><)(?P<tag_name>[-\w.:|]*)(?P<tag_contents>[\w\W]*)(?P<tag_end>>)"


def _diff(path, removed, added, start=10):
    lines = [f"diff --git a/{path} b/{path}", f"--- a/{path}", f"+++ b/{path}",
             f"@@ -{start},2 +{start},2 @@", " x = 1"]
    lines += [f"-{r}" for r in removed] + [f"+{a}" for a in added]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- rule 1: the trigger
def test_fires_on_an_edited_existing_pattern():
    assert bp.modified_patterns(EDITED) == [{"file": "rich/highlighter.py", "line": 85, "old": OLD_TAG}]


def test_silent_on_a_brand_new_pattern():
    assert bp.modified_patterns(ADDED) == []
    assert bp.probe_rule(ADDED, [{"id": "C1", "text": "keeps other keywords unchanged", "expect": "same"}]) == ""


def test_new_pattern_next_to_an_unrelated_removed_line_stays_silent():
    d = _diff("pkg/lex.py", ["    x = 2"], ["    (r'(CROSS|OUTER)\\s+APPLY(?![\\w$#])', Keyword),"])
    assert bp.modified_patterns(d) == []


def test_edited_pattern_in_a_synthetic_diff_fires_and_unrelated_pattern_does_not():
    d = _diff("pkg/lex.py", ["P = re.compile(r'<(\\w+)>[\\w\\W]*</\\1>')"],
              ["P = re.compile(r'<(\\w+)>[\\w\\W]*?</\\1>(?=\\s|$)')"])
    assert [m["old"] for m in bp.modified_patterns(d)] == [r"<(\w+)>[\w\W]*</\1>"]
    far = _diff("pkg/lex.py", ["P = re.compile(r'<(\\w+)>[\\w\\W]*</\\1>')"], ["Q = re.compile(r'\\d{4}-\\d{2}')"])
    assert bp.modified_patterns(far) == []


def test_unchanged_pattern_on_a_rewrapped_line_does_not_fire():
    d = _diff("pkg/lex.py", ["P = re.compile(r'a+b')"], ["P = re.compile(", "    r'a+b')"])
    assert bp.modified_patterns(d) == []


def test_plain_string_outside_a_re_call_is_not_a_pattern():
    d = _diff("pkg/fmt.py", ['SEP = "a|b"'], ['SEP = "a|c"'])
    assert bp.modified_patterns(d) == []
    # the same literal passed straight to a re function is a pattern
    d = _diff("pkg/fmt.py", ['SEP = re.compile("a|b")'], ['SEP = re.compile("a|c")'])
    assert [m["old"] for m in bp.modified_patterns(d)] == ["a|b"]


def test_pattern_split_across_adjacent_literals_stays_silent():
    d = _diff("pkg/lex.py", ["    P = re.compile(r'<(\\w+)>[\\w\\W]*</\\1>')"],
              ["    P = re.compile(r'<(\\w+)>'", "                   r'[\\w\\W]*</\\1>')"])
    assert bp.modified_patterns(d) == []
    one_line = _diff("pkg/lex.py", ["P = (r'a[\\w\\W]*' r'b')"], ["P = (r'a[\\w\\W]*b')"])
    assert bp.modified_patterns(one_line) == []
    # an edit hidden in the split is still an edit
    edited = _diff("pkg/lex.py", ["    P = re.compile(r'<(\\w+)>[\\w\\W]*</\\1>')"],
                   ["    P = re.compile(r'<(\\w+)>'", "                   r'[\\w\\W]*?</\\1>(?=\\s|$)')"])
    assert [m["old"] for m in bp.modified_patterns(edited)] == [r"<(\w+)>[\w\W]*</\1>"]


@pytest.mark.parametrize("path", ["tests/helpers.py", "pkg/testing/util.py",
                                  "tests/test_lex.py", "pkg/test_lex.py", "pkg/conftest.py", "README.md"])
def test_patterns_in_tests_and_non_python_files_are_ignored(path):
    d = _diff(path, ["P = r'a[\\w\\W]*b'"], ["P = r'a[\\w\\W]*?b'"])
    assert bp.modified_patterns(d) == []


# ---------------------------------------------------------------- rule 2: the prompt paragraph
def test_prompt_asks_for_inputs_just_past_the_old_boundary():
    rule = bp.probe_rule(EDITED, SAVED["claims_extracted"])
    assert "just past the boundary of the old match" in rule
    assert '"<Widget>\\nnext"' in rule and "not a bare trailing newline" in rule
    assert "followed by a space" in rule and "by other text" in rule
    assert "rich/highlighter.py line 85" in rule and OLD_TAG in rule.replace("\\\\", "\\")


def test_prompt_shows_base_side_text_only():
    rule = bp.probe_rule(EDITED, SAVED["claims_extracted"])
    assert "(?=<|$)" not in rule and "[\\w\\W]*?" not in rule.replace("\\\\", "\\")
    assert "content1" not in rule and "test_repr_highlighter_adjacent_tags" not in rule


def test_prompt_suggests_links_but_does_not_make_them():
    rule = bp.probe_rule(EDITED, SAVED["claims_extracted"])
    assert "among C2 that say behaviour is kept, if one does" in rule
    assert "empty claims list" in bp.probe_rule(EDITED, [])


# ---------------------------------------------------------------- rule 3: re-runs of the PR's own test
def test_claims_that_only_rerun_the_prs_test_are_not_suggested():
    claims = [{"id": "C2", "text": "preserves existing behavior for non-adjacent tags", "expect": "same"},
              {"id": "C4", "text": "The regression test passes", "expect": "same"},
              {"id": "C5", "text": "test_repr_highlighter_adjacent_tags gives the same result", "expect": "same"},
              {"id": "C6", "text": "adjacent tags are split", "expect": "differs"},
              {"id": "C7", "text": "keeps other tags", "expect": "same", "testable": False}]
    assert bp.pr_test_names(EDITED) == {"test_repr_highlighter_adjacent_tags"}
    assert bp.eligible_claims(claims, EDITED) == ["C2"]


# ---------------------------------------------------------------- the saved catch, judged offline
def test_saved_expect_same_probe_on_a_trailing_space_is_a_false_claim():
    """The saved entry: claim C2 expects 'same'; on '<a>content</a> ' the base side keeps the four tag spans and the
    PR side keeps none, in all 3 runs. Judged again from those runs by plain code: false_claim, a red label (needs
    attention), for the lost highlighting. The tag alone at the end of the text is unchanged."""
    item = probes.rejudge_entry({k: SAVED[k] for k in ("id", "source", "target", "about", "claims", "runs")})
    labels = {o["name"]: o["label"] for o in item["observations"]}
    assert labels == {"C2.single": "proven", "C2.space_after": "false_claim"}
    assert COLOUR[FindingLabel.FALSE_CLAIM] == "red"
    tag = {"repr.tag_start", "repr.tag_name", "repr.tag_contents", "repr.tag_end"}
    for run in SAVED["runs"]["main"]:
        assert tag <= {s[2] for s in run["C2.space_after"]}
    for run in SAVED["runs"]["pr"]:
        assert not tag & {s[2] for s in run["C2.space_after"]}
    assert SAVED["verdict"] == "needs_attention"
    assert bp.eligible_claims(SAVED["claims_extracted"], EDITED) == ["C2"]


# ---------------------------------------------------------------- wiring into probe generation
class _Stub(model_provider.Provider):
    name = "stub"

    def __init__(self):
        super().__init__()
        self.prompts = {}

    def complete_json(self, task, system, user, schema, ctx):
        self.prompts[task] = system
        self._remember(task, True)
        if task == "claims":
            return {"claims": [dict(c, source_quote=BODY) for c in SAVED["claims_extracted"]]}
        return {"probes": [{"id": "p1", "about": "tags", "claims": [{"id": "C2", "covers": ["C2.*"], "expect": "same"}],
                            "code": "print(json.dumps({'observations': {'C2.a': 1}}))\n"}]}


BODY = "The regex has been updated to correctly handle adjacent tags while preserving existing behavior."


def _gen(tmp_path, diff, product):
    base = tmp_path / "side-main"
    (base / "pkg").mkdir(parents=True)
    (base / "pkg" / "m.py").write_text("x = 1\n")
    prov = _Stub()
    res = model_probes.generate(prov, "o/r", 1, "Fix tags", BODY, {"pkg/m.py": base / "pkg" / "m.py"}, base,
                                [tmp_path / "side-pr"], tmp_path / "out", product=product, diff=diff)
    return prov.prompts["probes"], res


def test_generate_adds_the_rule_on_a_product_check_with_an_edited_pattern(tmp_path):
    prompt, res = _gen(tmp_path, EDITED, True)
    assert prompt.endswith(bp.probe_rule(EDITED, [dict(c, source_quote=BODY) for c in SAVED["claims_extracted"]]))
    assert res["boundary_rule"] == bp.modified_patterns(EDITED)


def test_plan_probes_records_the_boundary_rule(tmp_path, monkeypatch):
    import types

    from ops import daily_run
    seen = {}

    def fake_generate(*args, **kw):
        seen["diff"] = kw.get("diff")
        return {"probes": [], "claims": [], "rejected_claims": [], "errors": [],
                "boundary_rule": bp.modified_patterns(kw.get("diff"))}
    monkeypatch.setattr(model_probes, "generate", fake_generate)
    monkeypatch.setattr(daily_run.probes, "find_probes", lambda *x: [])
    item = {"pr": 1, "title": "Fix tags", "body": BODY, "files": {"all": []}, "diff": EDITED}
    a = types.SimpleNamespace(baseline=None, model_note=None, provider=object(), product_check=True, pr=1,
                              bench=None, no_probes=False)
    rec = {}
    daily_run.plan_probes("o/r", item, rec, tmp_path, [], tmp_path, a)
    assert seen["diff"] == EDITED
    assert rec["probe_plan"]["model_boundary_rule"] == bp.modified_patterns(EDITED)


@pytest.mark.parametrize("diff,product", [(ADDED, True), (None, True), (EDITED, False)])
def test_generate_leaves_the_prompt_alone_otherwise(tmp_path, diff, product):
    prompt, res = _gen(tmp_path, diff, product)
    assert "Modified pattern" not in prompt and "boundary_rule" not in res


# ---------------------------------------------------------------- safe cases: the trigger stays silent
# The 9 known-safe live cases (docs/decisions/2026-10-28-fixed-live-cases.md) and the 10 safe benchmark cases, 13
# distinct PRs. Their saved diffs are copied unchanged. The rule must not fire on any of them, so it cannot change
# their prompts. Only the known bug case fires (test_fires_on_an_edited_existing_pattern).
FIXED_SAFE = ["attrs-1647", "click-3878", "jsonschema-1515", "sqlparse-928", "toolz-650", "markupsafe-512",
              "rich-4143", "prettytable-524", "requests-7520"]
BENCH_SAFE = ["boltons-586", "isort-2737", "jsonschema-1515", "markupsafe-512", "prettytable-524", "requests-7586",
              "rich-4143", "sqlparse-928", "toolz-650", "urllib3-5328"]


def _safe_diff(case):
    return ADDED if case == "sqlparse-928" else (FX / "safe" / f"{case}.diff").read_text()


def test_the_safe_candidates_are_13_distinct_cases():
    assert len(FIXED_SAFE) == 9 and len(BENCH_SAFE) == 10 and len(set(FIXED_SAFE) | set(BENCH_SAFE)) == 13


@pytest.mark.parametrize("case", sorted(set(FIXED_SAFE) | set(BENCH_SAFE)))
def test_rule_stays_silent_on_every_safe_case(case):
    d = _safe_diff(case)
    assert d.startswith("diff --git")
    assert bp.modified_patterns(d) == [] and bp.probe_rule(d, []) == ""


@pytest.mark.parametrize("case", sorted(set(FIXED_SAFE) | set(BENCH_SAFE)))
def test_seeded_boundary_claim_stays_silent_on_every_safe_case(case):
    """poc/boundary_claims seeds nothing on a safe case, even with a claim that says behaviour is preserved."""
    from poc import boundary_claims
    d = _safe_diff(case)
    claim = {"id": "C1", "text": "Fixes the bug while preserving existing behavior.", "testable": True}
    assert boundary_claims.seed([claim], bp.modified_patterns(d), bp.pr_test_names(d)) == []
