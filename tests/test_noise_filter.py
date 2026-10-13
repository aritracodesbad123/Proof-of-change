"""Noise filter: run-to-run changes are ignored; warning-only differences never count on their own."""
from poc import probes


def _item(*obs):
    return {"id": "p", "observations": [{"name": n, "label": lab, "claim": None} for n, lab in obs]}


def test_flaky_observation_is_ignored_as_noise():
    s = probes.summarize([_item(("a.count", "flaky"), ("b", "no_difference"))])
    assert s["flagged"] == [] and s["ignored_noise"] == ["a.count"] and "noise" in s["reason"]


def test_warning_only_difference_does_not_count():
    s = probes.summarize([_item(("x.warning_raised", "unmentioned"), ("y", "no_difference"))])
    assert s["flagged"] == [] and s["ignored_warning_only"] == ["x.warning_raised"]


def test_warning_difference_with_a_real_difference_still_counts():
    s = probes.summarize([_item(("x.warning_raised", "unmentioned"), ("y.value", "unmentioned"))])
    assert {f["name"] for f in s["flagged"]} == {"x.warning_raised", "y.value"}


def test_real_difference_still_flags():
    s = probes.summarize([_item(("y.value", "false_claim"))])
    assert len(s["flagged"]) == 1 and s["ignored_noise"] == []
