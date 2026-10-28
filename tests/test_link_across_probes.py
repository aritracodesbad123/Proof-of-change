from poc import probes

FL = probes.FindingLabel


def _item(pid, claims, main, pr):
    spec = {"id": pid, "source": "model", "claims": claims}
    runs = {"main": [dict(main) for _ in range(3)], "pr": [dict(pr) for _ in range(3)]}
    return {"id": pid, "claims": claims, "observations": probes.judge(spec, runs)}


C1 = [{"id": "C1", "text": "x echoes ^D", "covers": ["C1.out"], "expect": "differs"}]
C2 = [{"id": "C2", "text": "y echoes ^Z", "covers": ["C2.out"], "expect": "differs"}]
M, P = {"C1.out": 4, "C2.out": 26}, {"C1.out": 94, "C2.out": 90}


def _obs(items, pid, name):
    return next(o for it in items if it["id"] == pid for o in it["observations"] if o["name"] == name)


def test_difference_proven_in_another_probe_is_advisory():
    items = probes.link_across_probes([_item("model-p1", C1, M, P), _item("model-p2", C2, M, P)])
    o = _obs(items, "model-p1", "C2.out")
    assert o["label"] == FL.UNMENTIONED_CHANGE.value and o["advisory"] and o["linked_by"] == "sibling"
    assert not probes.summarize(items)["flagged"]


def test_different_values_still_flag():
    items = probes.link_across_probes([_item("model-p1", C1, M, P), _item("model-p2", C2, M, dict(P, **{"C2.out": 91}))])
    assert not _obs(items, "model-p1", "C2.out").get("advisory")
    assert probes.summarize(items)["flagged"]


def test_a_single_probe_is_unchanged():
    items = [_item("model-p1", C1, M, P)]
    assert probes.link_across_probes(items) == items
    assert probes.summarize(items)["flagged"]


def test_same_claim_contradiction_proven_elsewhere_is_advisory():
    same = [{"id": "C2", "text": "the split is kept", "covers": ["C1.out"], "expect": "same"}]
    items = probes.link_across_probes([_item("model-p1", C1, M, P), _item("model-p2", same, M, P)])
    o = _obs(items, "model-p2", "C1.out")
    assert o["label"] == FL.FALSE_CLAIM.value and o["advisory"]
