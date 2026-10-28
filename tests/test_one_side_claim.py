from poc import probes

FL = probes.FindingLabel


def _obs(text, main="TypeError", pr="None"):
    claims = [{"id": "C1", "text": text, "covers": ["exc"], "expect": "same"}]
    spec = {"id": "model-p1", "source": "model", "claims": claims}
    runs = {"main": [{"exc": main}] * 3, "pr": [{"exc": pr}] * 3}
    return probes.judge(spec, runs)[0]


def test_before_the_fix_claim_is_advisory():
    o = _obs("Before the fix, validating a Decimal raises a TypeError.")
    assert o["label"] == FL.FALSE_CLAIM.value and o["advisory"] and o["linked_by"] == "one_side_claim"
    assert not probes.summarize([{"id": "model-p1", "observations": [o]}])["flagged"]


def test_after_the_fix_claim_is_advisory():
    assert _obs("After the fix, the fallback rejects genuine non-multiples.").get("advisory")


def test_keep_claims_still_flag():
    for text in ("After the PR, the highlighter preserves existing behavior for other tags.",
                 "Before the fix and after it, plain entries still match.",
                 "Results stay the same after this change.",
                 "After the change, a request to another port will NOT bypass the proxy."):
        o = _obs(text)
        assert o["label"] == FL.FALSE_CLAIM.value and not o.get("advisory"), text


def test_plain_same_claim_still_flags():
    assert not _obs("Plain IPv4 addresses match as configured.").get("advisory")
