from poc.batch_order import OrderLog, is_setup_failure, run_batch

OK = {"verdict": "verified", "reason": "fine"}
SETUP = {"verdict": "could_not_verify", "reason": "main side install failed: no wheel"}


def test_setup_and_lookup_failures_are_skipped_then_retried_at_the_end(tmp_path):
    order = []
    lookups = {"a": [True], "b": [False, True], "c": [True, True]}
    runs = {"a": [OK], "b": [dict(OK)], "c": [dict(SETUP), dict(OK)]}
    diagnosed = []

    def lookup(i):
        order.append(("lookup", i))
        return lookups[i].pop(0)

    def run(i):
        order.append(("run", i))
        return dict(runs[i].pop(0), pr=i)

    log = OrderLog(tmp_path / "order.jsonl")
    out = run_batch(["a", "b", "c"], str, lookup, run, diagnose=lambda i, w: diagnosed.append(i), log=log)
    assert [r["pr"] for r in out] == ["a", "b", "c"]
    # pass 1: a runs, b skipped at lookup, c fails setup; then the end pass
    assert order[:5] == [("lookup", "a"), ("run", "a"), ("lookup", "b"), ("lookup", "c"), ("run", "c")]
    assert diagnosed == ["b", "c"]
    assert all(r["verdict"] == "verified" for r in out)
    assert (tmp_path / "order.jsonl").read_text().count("skipped for the end pass") == 2


def test_three_failed_tries_end_as_could_not_verify():
    tries = []

    def run(i):
        tries.append(i)
        return dict(SETUP)

    out = run_batch(["x"], str, lambda i: True, run, diagnose=lambda i, w: None)
    assert len(tries) == 4  # first pass plus 3 end-pass tries
    assert out[0]["verdict"] == "could_not_verify" and "after 3 tries" in out[0]["reason"]


def test_lookup_that_never_works_gives_could_not_verify_without_running():
    ran = []
    out = run_batch(["x"], str, lambda i: False, lambda i: ran.append(i),
                    give_up=lambda i, why: {"pr": i, "verdict": None, "reason": why})
    assert ran == [] and out[0]["verdict"] == "could_not_verify"


def test_a_test_failure_is_not_a_setup_failure():
    assert not is_setup_failure({"verdict": "needs_attention", "reason": "install failed? no, a test failed"})
    assert is_setup_failure(SETUP)


def test_runner_batch_order_logs_and_stages_fixes(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import ops.daily_run as dr

    results = {1: [{"verdict": "could_not_verify", "reason": "main side install failed: x"},
                   {"verdict": "verified", "reason": "ok"}],
               2: [{"verdict": "needs_attention", "reason": "a test fails"}]}

    def fake_test_pr(repo, cfg, c, rdir, workroot, a, machine):
        r = dict(results[c["pr"]].pop(0))
        return r | {"repo": repo, "pr": {"number": c["pr"], "head_sha": "abc"}, "tested_at_ist": "t",
                    "duration_s": {"total_wall": 1}}

    monkeypatch.setattr(dr, "test_pr", fake_test_pr)
    monkeypatch.setattr(dr, "gate", lambda r: r)
    monkeypatch.setattr(dr, "_batch_lookup", lambda repo, cfg: True)
    staged = []
    monkeypatch.setattr(dr, "_batch_diagnose", lambda a, item, why: staged.append(why))
    queue = [("o/r", {"pkg": "r"}, {"pr": n, "title": "t"}) for n in (1, 2)]
    seen = {"prs": {}}
    out = dr._run_batch_order(queue, tmp_path, tmp_path, SimpleNamespace(), {}, seen, [])
    assert [r["pr"]["number"] for r in out] == [2, 1]
    assert staged and "install failed" in staged[0]
    assert "end pass" in (tmp_path / "batch-order.jsonl").read_text()
    assert seen["prs"]["o/r"]["1"]["verdict"] == "verified"


def test_diagnosis_is_staged_per_pr_and_from_trusted_pages_only(monkeypatch):
    from types import SimpleNamespace

    import ops.daily_run as dr
    from poc import demo_helper
    monkeypatch.setattr(demo_helper, "live_fetch", lambda q: {"ok": True, "results": [
        {"url": "https://github.com/o/r/blob/main/INSTALL.md", "content": "o r: apt-get install liba-dev"},
        {"url": "https://blog.example/fix", "content": "o r: apt-get install libevil"}]})
    monkeypatch.setattr(demo_helper, "apt_available", lambda name, run=None: True)
    a = SimpleNamespace()
    dr._batch_diagnose(a, ("o/r", {"dist": "r"}, {"pr": 7}), "ImportError: liba.so.1: cannot open shared object file")
    assert a.batch_fix_system == {"o/r#7": ["liba-dev"]}
