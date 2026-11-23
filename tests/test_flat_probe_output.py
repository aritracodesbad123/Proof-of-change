"""A bare observations object is read only when its shape is unambiguous, and one retry follows a parse failure.

prettytable #558 printed a flat JSON object whose keys are the observation ids. That object is now the
observations. A wrapped object still parses. An ambiguous object, a traceback, and stderr are not observations.
When both sides still fail to parse, the probe is sent back once with the exact error and the output contract.
"""
import json
import os
import sys
from pathlib import Path

from ops import daily_run
from poc import freeze, model_probes, probes

# The two objects saved as probe.error for prettytable #558. The probe printed them with no "observations" key.
PRETTYTABLE_MAIN = (
    '{"c1.shape_access": "AttributeError", "c2.shape0": "AttributeError", "c2.shape1": "AttributeError", '
    '"c2.shape2": "AttributeError", "c2.shape3": "AttributeError", "c3.shape_base": "AttributeError", '
    '"c3.shape_header_false": "AttributeError", "c3.shape_header_true": "AttributeError", '
    '"c3.shape_fields_set": "AttributeError", "c3.shape_slice_set": "AttributeError", '
    '"c4.shape_docstring": "TypeError", "c4.shape_doc_mentions_rowcount": "TypeError", '
    '"c4.shape_doc_mentions_colcount": "TypeError"}'
)
PRETTYTABLE_PR = (
    '{"c1.shape_access": [0, 0], "c2.shape0": [0, 0], "c2.shape1": [0, 1], "c2.shape2": [1, 1], '
    '"c2.shape3": [2, 1], "c3.shape_base": [2, 1], "c3.shape_header_false": [2, 1], '
    '"c3.shape_header_true": [2, 1], "c3.shape_fields_set": [2, 1], "c3.shape_slice_set": null, '
    '"c4.shape_docstring": "Return the number of stored data rows and columns.", '
    '"c4.shape_doc_mentions_rowcount": false, "c4.shape_doc_mentions_colcount": false}'
)
ERR = probes.PROBE_ERROR


def test_prettytable_flat_output_parses_and_wrapped_output_still_parses():
    main = json.loads(PRETTYTABLE_MAIN)
    pr = json.loads(PRETTYTABLE_PR)
    assert probes.observations_of(PRETTYTABLE_MAIN, 0) == main
    assert probes.observations_of("noise\n" + PRETTYTABLE_PR + "\n", 0) == pr
    # The same values inside the wrapper are unchanged.
    wrapped = json.dumps({"observations": pr})
    assert probes.observations_of(wrapped, 0) == pr
    assert probes.observations_of(wrapped, 1) == dict(pr, **{ERR: {"exit_code": 1}})
    # Only the last line is read. The earlier object is not merged in.
    assert probes.observations_of('{"c1.a": 1}\n{"c1.b": 2}\n', 0) == {"c1.b": 2}
    # A Python literal of a bare observation-id map is read when literal output is on.
    assert probes.observations_of("{'c1.a': 1, 'c2.b': None}\n", 0, literal_output=True) == {"c1.a": 1, "c2.b": None}
    # Names the probe was asked to cover, with no wrapper key, are observations. The same map with no covers is not.
    asked = '{"rows": 1, "cols": 2}'
    assert probes.observations_of(asked, 0) == {ERR: {
        "crash": "ambiguous output", "reason": "the JSON object's keys are not observation ids", "exit_code": 0}}
    assert probes.observations_of(asked, 0, covers=["rows", "cols"]) == {"rows": 1, "cols": 2}


def test_ambiguous_garbage_traceback_and_stderr_are_not_observations(tmp_path):
    assert ERR in probes.observations_of('{"no": "observations"}', 0)
    assert probes.output_parse_failure(probes.observations_of('{"no": "observations"}', 0))
    # A mix is rejected whole. The observation-id key is not kept on its own.
    mixed = probes.observations_of('{"c1.a": 1, "no": 2}', 0)
    assert set(mixed) == {ERR} and "c1.a" not in mixed
    # A key the probe was not asked for is not dropped. The whole object is rejected.
    partial = probes.observations_of('{"rows": 1, "cols": 2}', 0, covers=["rows"])
    assert set(partial) == {ERR} and "rows" not in partial
    # A wrapper key makes the object a status report. Its other keys are not observations.
    assert set(probes.observations_of('{"error": "boom", "c1.a": 1}', 0)) == {ERR}
    # A traceback is not scraped, even when an observation-shaped fragment sits in the text.
    tb = 'Traceback (most recent call last):\n  File "p.py", line 1, in <module>\nValueError: {"c1.v": 1}\n'
    assert ERR in probes.observations_of(tb, 1)
    assert probes.output_parse_failure(probes.observations_of(tb, 1)) is None  # non-zero exit is a crash, not a retry
    # Stderr is not parsed. A JSON object printed only there produces no observations.
    p = tmp_path / "err.py"
    p.write_text('PROBE = {"id": "err", "target": "o/r#1", "about": "x", "claims": []}\n'
                 'import sys\nsys.stderr.write("{\\"c1.a\\": 1}\\n")\n')
    obs, log, _ = probes.run_once(p, Path(sys.executable), tmp_path, {"PATH": os.environ["PATH"]}, 30)
    assert set(obs) == {ERR}
    assert "c1.a" not in obs and "stderr" in log


def test_unparsed_output_is_retried_once_and_a_bad_retry_stays_an_error(tmp_path):
    prdir = tmp_path / "run"
    gen = freeze.generator("model", model="m", provider="recorded")
    path = prdir / "model-probes" / "model-p1.py"
    path.parent.mkdir(parents=True)
    path.write_text(model_probes.probe_file(
        {"id": "p1", "about": "a", "claims": [], "code": 'print("{\\"no\\": \\"observations\\"}")\n'},
        "o/r#1", {}, gen["label"]))
    py = Path(sys.executable)
    env = {"PATH": os.environ["PATH"], "PYTHONPATH": ""}
    it = probes.run_probe(path, {"main": py, "pr": py}, prdir, tmp_path / "cwd",
                          {"main": env, "pr": env}, runs=1, source="model", literal_output=True)
    it["path"] = str(path.relative_to(prdir))
    it["freeze"] = freeze.freeze(path, gen, None)
    raw = prdir / "model-probes" / "model-p1.rejected-main-1.stdout"
    assert raw.is_file() and "observations" in raw.read_text()
    assert probes.output_parse_failure(it["runs"]["main"][0])
    calls = []

    class Provider:
        def complete_json(self, kind, prompt, user, schema, ctx):
            calls.append((prompt, user))
            return {"probes": [{"id": "p1", "about": "a", "claims": [], "code": "print('still bad')\n"}]}

    def run_one(x, started):
        freeze.verify(Path(x["path"]), x["freeze"], started)
        return probes.run_probe(Path(x["path"]), {"main": py, "pr": py}, prdir, tmp_path / "cwd2",
                                {"main": env, "pr": env}, runs=1, source="model", literal_output=True)

    items = [it]
    out = daily_run.rewrite_crashed_probes(items, prdir, type("A", (), {"provider": Provider()})(), run_one)
    assert len(calls) == 1
    assert "Exact parse error:" in calls[0][1] and probes.OUTPUT_CONTRACT in calls[0][1]
    assert "ambiguous output" in calls[0][1]
    rejected = prdir / "model-probes" / "model-p1.rejected.py"
    assert rejected.is_file() and path.is_file() and rejected.read_text() == path.read_text()
    assert out["probes"][0]["rejected_probe"].endswith("model-p1.rejected.py")
    assert "model-p1.rejected-main-1.stdout" in out["probes"][0]["rejected_stdout"]
    # The retry printed garbage. That run is an error, not a made-up observation.
    for side in ("main", "pr"):
        (run,) = items[0]["runs"][side]
        assert set(run) == {ERR}
        assert probes.output_parse_failure(run)
