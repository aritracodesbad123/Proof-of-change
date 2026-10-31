"""Three fixes from the 2026-10-31 re-run of commit 06e3e5c. No model call and no project run.

sqlparse #941 and loguru #1536 froze probes with claims: [] after the retry still linked nothing.
sqlparse #941 split "Don't raise IndexError" into c1_exception and c1_result, so the title claim saw no shape.
toolz #654 failed the claims call with TimeoutError and did not try again.
"""
import ast
import json
from pathlib import Path

from poc import model_probes, model_provider, probes

FX = Path(__file__).parent / "fixtures" / "rerun_06e3e5c"
SQL = json.loads((FX / "sqlparse_c1.json").read_text())
LOG = json.loads((FX / "loguru_probe.json").read_text())
TOOLZ = json.loads((FX / "toolz_claims_error.json").read_text())

SQL_CODE = (
    "import json\n"
    "obs = {'c1_exception': 'IndexError', 'c1_result': '( AS )'}\n"
    "print(json.dumps({'observations': obs}))\n"
)
LOG_CODE = (
    "import json\n"
    "obs = {}\n"
    "for name in ('ascii_count', 'nonascii_count'):\n"
    "    obs[f'c1.{name}'] = 1\n"
    "obs['c2.count.newline_None'] = 4\n"
    "obs['c6.none_matches_os_linesep'] = True\n"
    "print(json.dumps({'observations': obs}))\n"
)


def _claims(*ids, expect="differs"):
    return [{"id": cid, "text": cid, "expect": expect, "testable": True} for cid in ids]


def test_fixtures_have_no_machine_paths():
    blob = (FX / "sqlparse_c1.json").read_text() + (FX / "loguru_probe.json").read_text()
    blob += (FX / "toolz_claims_error.json").read_text()
    assert "/home/" not in blob and "/Users/" not in blob and "/opt/" not in blob


def test_about_probe_id_and_observation_prefix_name_only_those_claims():
    sql = model_probes.fill_signalled_claims(
        {"id": "probe-c1", "about": "C1", "claims": [], "code": SQL_CODE},
        _claims("C1") + _claims("C2", expect="same") + _claims("C10"))
    assert [c["id"] for c in sql["claims"]] == ["C1"]
    assert sql["claims"][0]["covers"] == ["c1_*"]
    assert sql["claims"][0]["expect"] == "differs"
    # probe1 is not claim C1. The printed prefixes are.
    log = model_probes.fill_signalled_claims(
        {"id": "probe1", "about": LOG["probe"]["about"], "claims": [], "code": LOG_CODE},
        _claims("C1", "C2", "C3", "C4", "C5", "C6"))
    assert [c["id"] for c in log["claims"]] == ["C1", "C2", "C6"]
    assert log["claims"][0]["covers"] == ["c1.*"]
    assert log["claims"][1]["covers"] == ["c2.*"]
    lone = model_probes.fill_signalled_claims(
        {"id": "probe1", "about": "counts bytes", "claims": [], "code": "obs = {'f.a': 1}\n"},
        _claims("C1"))
    assert lone["claims"] == []
    assert model_probes.fill_signalled_claims(
        {"id": "probe-c10", "about": "C10", "claims": [], "code": "obs = {'c10_x': 1}\n"},
        _claims("C1"))["claims"] == []


def test_a_named_claim_is_not_replaced_by_the_signals():
    kept = {"id": "probe-c1", "about": "C1", "code": SQL_CODE,
            "claims": [{"id": "C2", "covers": ["c2_*"], "expect": "same"}]}
    assert model_probes.fill_signalled_claims(kept, _claims("C1") + _claims("C2", expect="same")) is kept


class _Scripted(model_provider.Provider):
    name = "scripted"

    def __init__(self, answers):
        super().__init__()
        self.answers = list(answers)

    def complete_json(self, task, system, user, schema, ctx):
        if task == "claims":
            return {"claims": [
                {"id": "C1", "text": "no longer raises IndexError", "source_quote": SQL["title"],
                 "testable": True, "expect": "differs"},
                {"id": "C2", "text": "well-formed groups stay the same",
                 "source_quote": "The output for the reported input is now the input unchanged.",
                 "testable": True, "expect": "same"}]}
        return self.answers.pop(0)


def test_after_the_retry_still_links_nothing_the_sqlparse_probe_is_filled(tmp_path):
    blank = {"probes": [{"id": "probe-c1", "about": "C1", "claims": [], "code": SQL_CODE}]}
    base = tmp_path / "base"
    (base / "sqlparse" / "filters").mkdir(parents=True)
    (base / "sqlparse" / "filters" / "others.py").write_text("x = 1\n")
    body = "The output for the reported input is now the input unchanged."
    out = model_probes.generate(
        _Scripted([blank, blank]), "andialbrecht/sqlparse", 941, SQL["title"], body,
        {"sqlparse/filters/others.py": base / "sqlparse" / "filters" / "others.py"}, base, [],
        tmp_path / "out")
    assert out["retried"]["kept_first_answer"] == "the retry linked no claim either"
    assert out["claims_filled"] == [{"id": "probe-c1", "claims": ["C1"]}]
    line = next(ln for ln in out["probes"][0]["path"].read_text().splitlines() if ln.startswith("PROBE = "))
    frozen = ast.literal_eval(line[len("PROBE = "):])
    assert [c["id"] for c in frozen["claims"]] == ["C1"]
    assert frozen["claims"][0]["covers"] == ["c1_*"]
    assert frozen["id"] == "model-probe-c1"


def _sql_item(claims):
    spec = {"id": SQL["probe"]["id"], "target": "andialbrecht/sqlparse#941", "about": SQL["probe"]["about"],
            "claims": claims, "source": "model"}
    runs = {"main": [dict(x) for x in SQL["runs"]["main"]], "pr": [dict(x) for x in SQL["runs"]["pr"]]}
    runs["main"] = [dict(row, other=1) for row in runs["main"]]
    runs["pr"] = [dict(row, other=2) for row in runs["pr"]]
    return probes.entry(spec, runs, None, [], "model", None)


def test_title_claim_covers_the_split_indexerror_pair_and_not_another_difference():
    item = _sql_item([])
    labels = {o["name"]: o["label"] for o in item["observations"]}
    assert labels == {"c1_exception": "unmentioned", "c1_result": "unmentioned", "other": "unmentioned"}
    assert probes._shape(item["observations"][0]) == "IndexError"
    settled = probes.apply_title_claim({"status": "ran", "items": [item]}, SQL["title"])
    by_name = {o["name"]: o for o in settled["items"][0]["observations"]}
    assert by_name["c1_exception"]["label"] == "proven" and by_name["c1_exception"]["claim"] == "title"
    assert by_name["c1_result"]["label"] == "proven" and by_name["c1_result"]["claim"] == "title"
    assert by_name["other"]["label"] == "unmentioned" and by_name["other"].get("claim") is None


def test_the_split_pair_links_claim_c1_when_the_covers_do_not_match():
    claim = {"id": "C1", "text": SQL["claims"][0]["text"], "covers": ["nomatch"], "expect": "differs",
             "source": "PR description"}
    item = _sql_item([claim])
    by_name = {o["name"]: o for o in item["observations"]}
    assert by_name["c1_exception"]["label"] == "proven" and by_name["c1_exception"]["claim"] == "C1"
    assert by_name["c1_result"]["label"] == "proven" and by_name["c1_result"]["claim"] == "C1"
    assert by_name["c1_exception"]["linked_by"] == "shape"
    assert probes._shape(by_name["c1_exception"]) == "IndexError"
    assert probes._shape(by_name["c1_result"]) == "IndexError"
    assert by_name["other"]["label"] == "unmentioned"
    same = _sql_item([dict(claim, expect="same")])
    assert {o["label"] for o in same["observations"]} == {"unmentioned"}


class _Timeouts(model_provider.Provider):
    name = "scripted"

    def __init__(self, errors):
        super().__init__()
        self.errors, self.calls = list(errors), 0

    def complete_json(self, task, system, user, schema, ctx):
        self.calls += 1
        assert task == "claims"
        if self.errors:
            raise model_provider.ProviderError(self.errors.pop(0))
        return {"claims": [{"id": "C1", "text": "order is kept", "source_quote": "Preserve insertion order",
                            "testable": False, "expect": "differs"}]}


def test_claims_timeout_is_retried_once_and_other_errors_are_not(tmp_path):
    assert TOOLZ["error"].endswith("TimeoutError")
    once = _Timeouts([TOOLZ["error"]])
    out = model_probes.generate(once, "pytoolz/toolz", 654, "Preserve insertion order", "", {}, tmp_path, [],
                                tmp_path / "out")
    assert once.calls == 2 and out["errors"] == []
    assert out["claims_timeout_retry"] == {"why": "TimeoutError", "second": "ok"}
    assert [c["id"] for c in out["claims"]] == ["C1"]
    twice = _Timeouts([TOOLZ["error"], TOOLZ["error"]])
    failed = model_probes.generate(twice, "pytoolz/toolz", 654, "t", "", {}, tmp_path, [], tmp_path / "again")
    assert twice.calls == 2 and failed["claims"] == []
    assert failed["errors"] == [TOOLZ["error"]]
    assert failed["claims_timeout_retry"]["second"] == "failed"
    other = _Timeouts(["nebius claims request failed: HTTPError"])
    missed = model_probes.generate(other, "pytoolz/toolz", 654, "t", "", {}, tmp_path, [], tmp_path / "http")
    assert other.calls == 1 and "claims_timeout_retry" not in missed
    assert missed["errors"] == ["nebius claims request failed: HTTPError"]
