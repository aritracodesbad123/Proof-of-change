"""The same exception on both sides is never proof, once side folder names are removed.

The fixture is the shape of invoke pull request 1097: both sides raise ParseError with the same text, and the
traceback names side-main on one side and side-pr on the other. That path is not a difference in behaviour.
"""
import json
from pathlib import Path

from ops import daily_run
from poc import diff, probes
from poc.verdict import FindingLabel

FIXTURE = Path(__file__).parent / "fixtures" / "identical_exceptions" / "invoke_1097.json"
DIFFERS = {"id": "C1", "text": "the result changes", "covers": ["c1*"], "expect": "differs"}
SAME = {"id": "C1", "text": "the result stays", "covers": ["c1*"], "expect": "same"}


def _load():
    return json.loads(FIXTURE.read_text())


def _judge(main, pr, claims):
    spec = {"id": "p", "target": "pyinvoke/invoke#1097", "about": "missing argument", "claims": claims}
    it = probes.entry(spec, {"main": [main] * 3, "pr": [pr] * 3}, {"main": ["m"], "pr": ["p"]}, [], "model", None)
    return it


def test_side_folder_names_are_not_a_difference():
    assert diff.normalise("work/side-main/invoke/parser/parser.py") == "work/<side>/invoke/parser/parser.py"
    assert diff.normalise("work/side-pr/invoke/parser/parser.py") == "work/<side>/invoke/parser/parser.py"
    for kind in ("venv", "cwd", "home", "out"):
        assert diff.normalise(f"work/{kind}-main/pkg") == diff.normalise(f"work/{kind}-pr/pkg")
    # A real word is kept. Only the harness folder names are removed.
    assert diff.normalise("main branch") != diff.normalise("pr branch")


def test_same_parseerror_is_not_proof():
    data = _load()
    assert data["main"]["c1.error"]["message"] != data["pr"]["c1.error"]["message"]
    it = _judge(data["main"], data["pr"], [data["claim"]])
    (obs,) = it["observations"]
    assert obs["state"] == "same"
    assert obs["label"] == FindingLabel.NOT_TESTABLE.value
    assert obs.get("probe_broken")
    assert obs["label"] != FindingLabel.PROVEN.value
    assert probes.summarize([it])["proven_claims"] == []
    rec = {"verdict": "verified", "reason": "tests pass", "baseline": "tests+probes",
           "probes": {"status": "ran", "items": [it]}}
    out = daily_run.gate(rec)
    assert out["verdict"] == "could_not_verify"
    assert "broken" in out["reason"]


def test_a_real_message_change_is_still_a_difference():
    data = _load()
    pr = json.loads(json.dumps(data["pr"]))
    pr["c1.error"]["message"] = pr["c1.error"]["message"].replace("'param_1'", "'param-1'")
    it = _judge(data["main"], pr, [data["claim"]])
    (obs,) = it["observations"]
    assert obs["state"] == "differs"
    assert obs["label"] == FindingLabel.PROVEN.value
    assert not obs.get("probe_broken")


def test_long_traceback_and_unexpected_exit_are_the_same_crash():
    data = _load()
    pad = "\n  File \"work/side-main/invoke/tasks.py\", line 1, in run"
    # The side name is what differs; the padding only makes the text longer than the short-line matcher.
    main_tb = data["main"]["c1.error"]["message"] + pad * 20
    pr_tb = data["pr"]["c1.error"]["message"] + pad.replace("side-main", "side-pr") * 20
    assert len(main_tb) > 500 and len(pr_tb) > 500
    it = _judge({"c1.error": main_tb}, {"c1.error": pr_tb}, [DIFFERS])
    (obs,) = it["observations"]
    assert obs["label"] == FindingLabel.NOT_TESTABLE.value and obs.get("probe_broken")
    crash = "UnexpectedExit: command failed\nFile \"work/cwd-{}/tasks.py\", line 4"
    it = _judge({"c1.error": crash.format("main")}, {"c1.error": crash.format("pr")}, [SAME])
    (obs,) = it["observations"]
    assert obs["state"] == "same" and obs.get("probe_broken")
    assert obs["label"] != FindingLabel.PROVEN.value


def test_a_path_inside_a_normal_result_can_still_prove_sameness():
    main = {"c1.value": {"n": 1, "where": "work/side-main/out"}}
    pr = {"c1.value": {"n": 1, "where": "work/side-pr/out"}}
    it = _judge(main, pr, [SAME])
    (obs,) = it["observations"]
    assert obs["state"] == "same" and obs["label"] == FindingLabel.PROVEN.value
    assert not obs.get("probe_broken")


def test_different_exception_types_stay_a_difference():
    main = {"c1.error": {"raises": "ParseError", "message": "work/side-main/invoke/parser/parser.py"}}
    pr = {"c1.error": {"raises": "TypeError", "message": "work/side-pr/invoke/parser/parser.py"}}
    it = _judge(main, pr, [DIFFERS])
    (obs,) = it["observations"]
    assert obs["state"] == "differs" and obs["label"] == FindingLabel.PROVEN.value
    assert not obs.get("probe_broken")
