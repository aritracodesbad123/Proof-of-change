"""The choke point between prompts and model providers (poc/model_gate.py): a leaking bundle never reaches the
provider. Synthetic answer key only."""
import pytest

from poc import leakage
from poc.leakage import LeakageError
from poc.model_gate import Gate, GatedProvider

ANSWERS = "tests/fixtures/bench/answers-synthetic.csv"


class Spy(GatedProvider):
    name = "spy"

    def __init__(self, gate):
        super().__init__(gate)
        self.sent = []

    def _call(self, task, system, user, schema, ctx):
        self.sent.append((task, system, user, dict(ctx)))
        return {"ok": True}


def gate(**kw):
    return Gate(leakage.fingerprints(ANSWERS), pr="example-org/widgets#4100", **kw)


def test_clean_request_reaches_the_provider():
    p = Spy(gate())
    assert p.complete_json("claims", "Extract claims.", "Use handle settings when picking a pool", {}) == {"ok": True}
    assert len(p.sent) == 1 and p.gate.log[-1]["ok"]


@pytest.mark.parametrize("system,user,ctx", [
    ("Extract claims.", "Body: subclasses fail with 'Unsupported handle scheme zebra'", {}),
    ("Hint: see widgets#4242", "Use handle settings", {}),
    ("Write probes.", "ok", {"files": {"src/widgets/a.py": "# https://github.com/example-org/widgets/issues/4242\n"}}),
])
def test_leaking_bundle_never_reaches_the_provider(system, user, ctx):
    p = Spy(gate())
    with pytest.raises(LeakageError):
        p.complete_json("claims", system, user, {}, ctx)
    assert p.sent == [] and p.gate.log[-1]["ok"] is False


def test_new_side_only_file_never_reaches_the_provider():
    p = Spy(gate(base_files={"src/widgets/a.py"}, pr_files={"src/widgets/a.py", "src/widgets/new.py"}))
    with pytest.raises(LeakageError, match="only on the PR side"):
        p.complete_json("probes", "Write probes.", "ok", {}, {"files": {"src/widgets/new.py": "x = 1\n"}})
    assert p.sent == []


def test_no_gate_fails_closed():
    p = Spy(None)
    with pytest.raises(LeakageError, match="no firewall gate"):
        p.complete_json("claims", "s", "u", {})
    assert p.sent == []


def test_overriding_complete_json_is_rejected():
    with pytest.raises(TypeError, match="implement _call"):
        class Sneaky(GatedProvider):
            def complete_json(self, *a, **k):
                return {}


def test_gate_takes_fingerprints_not_an_answer_key_path():
    with pytest.raises(TypeError, match="Fingerprints"):
        Gate(ANSWERS)
    p = Spy(Gate.no_answer_key(pr="example-org/widgets#4100"))
    assert p.complete_json("claims", "s", "widgets#4242 is fine without a key", {}) == {"ok": True}
