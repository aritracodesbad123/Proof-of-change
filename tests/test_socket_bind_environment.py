"""A local server started by the tests gets its own loopback, and a bind error that also happens on the base
is the environment.

The fixtures are generic. They do not name a project, a package, or a fixed map from an error onto a package.
"""
import subprocess

import pytest

from guardrails import sandbox
from ops.daily_run import compare_sides, verdict_for
from ops.daily_run import tests_verdict as verdict_from_tests
from reports import pr_report

BIND = "failed on setup with \"OSError('failed to bind socket') [single exception in ExceptionGroup]\""
IN_USE = "OSError: [Errno 98] Address already in use"
TEARDOWN = "failed on teardown with \"pytest.PytestUnhandledThreadExceptionWarning: Exception in thread Thread-3"
ASSERTION = "AssertionError: expected 1"
SETUP_VALUE = "failed on setup with \"ValueError: I/O operation on closed file\""
OK = "pkg.mod::test_ok"
OLD = "pkg.mod::test_old"
NEW = "pkg.mod::test_new"


def _runs(main: dict, pr: dict) -> dict:
    return {"main": [main, main, main], "pr": [pr, pr, pr]}


def _passed(extra=None):
    row = {OK: ("passed", "")}
    if extra:
        row.update(extra)
    return row


def test_bind_on_both_sides_is_environment_not_needs_attention():
    main = _passed({OLD: ("error", BIND)})
    pr = _passed({OLD: ("error", BIND), NEW: ("error", BIND)})
    cmp = compare_sides(_runs(main, pr))
    assert NEW not in cmp["new_tests_failing"]
    assert cmp["regressions"] == []
    shared = [e for e in cmp["environment"] if e.get("kind") == "shared_error"]
    assert [e["test"] for e in shared] == [NEW]
    v, reason, _ = verdict_from_tests(cmp, None)
    assert v == "could_not_verify"
    assert "needs attention" not in reason
    assert "failed to bind a local socket" in reason
    assert "environment" in reason
    report = pr_report.decide({"verdict": v, "reason": reason, "comparison": cmp}, [])
    assert report["verdict"] == "COULD NOT VERIFY"
    assert report["action"] != "Reject"
    assert report["confidence"] == "Low"


def test_address_in_use_on_both_sides_is_the_same_environment_error():
    main = _passed({OLD: ("error", IN_USE)})
    pr = _passed({OLD: ("error", IN_USE), NEW: ("error", "OSError: [Errno 98] Address already in use")})
    cmp = compare_sides(_runs(main, pr))
    v, reason, _ = verdict_from_tests(cmp, None)
    assert NEW not in cmp["new_tests_failing"]
    assert v == "could_not_verify"
    assert "already in use" in reason


def test_pr_only_assertion_still_needs_attention():
    pr = _passed({NEW: ("failed", ASSERTION)})
    cmp = compare_sides(_runs(_passed(), pr))
    assert cmp["new_tests_failing"] == [NEW]
    v, reason, _ = verdict_from_tests(cmp, None)
    assert v == "needs_attention"
    assert "new test(s) fail" in reason
    report = pr_report.decide({"verdict": v, "reason": reason, "comparison": cmp}, [])
    assert report["action"] == "Reject"


def test_bind_only_on_the_pr_still_needs_attention():
    pr = _passed({NEW: ("error", BIND)})
    cmp = compare_sides(_runs(_passed(), pr))
    assert cmp["new_tests_failing"] == [NEW]
    assert verdict_from_tests(cmp, None)[0] == "needs_attention"


def test_setup_error_only_on_the_pr_still_needs_attention():
    main = _passed({OLD: ("error", BIND)})
    pr = _passed({OLD: ("error", BIND), NEW: ("error", SETUP_VALUE)})
    cmp = compare_sides(_runs(main, pr))
    assert cmp["new_tests_failing"] == [NEW]
    assert verdict_from_tests(cmp, None)[0] == "needs_attention"


def test_same_setup_error_on_the_base_is_environment():
    main = _passed({OLD: ("error", SETUP_VALUE)})
    pr = _passed({OLD: ("error", SETUP_VALUE), NEW: ("error", SETUP_VALUE)})
    cmp = compare_sides(_runs(main, pr))
    assert NEW not in cmp["new_tests_failing"]
    assert verdict_from_tests(cmp, None)[0] == "could_not_verify"


def test_assertion_beside_a_shared_bind_error_still_needs_attention():
    main = _passed({OLD: ("error", BIND)})
    pr = _passed({OLD: ("error", BIND), NEW: ("error", BIND), "pkg.mod::test_real": ("failed", ASSERTION)})
    cmp = compare_sides(_runs(main, pr))
    assert cmp["new_tests_failing"] == ["pkg.mod::test_real"]
    assert any(e["test"] == NEW for e in cmp["environment"])
    assert verdict_from_tests(cmp, None)[0] == "needs_attention"


def test_a_clean_run_stays_verified():
    cmp = compare_sides(_runs(_passed(), _passed()))
    assert verdict_from_tests(cmp, None)[0] == "verified"


def test_saved_record_with_more_failures_than_messages_is_environment():
    """A stored comparison keeps the first messages. When every one of them is the bind error, and the base
    recorded that exception, the failures whose text was not kept are the same error."""
    ids = [f"pkg.mod::test_case_{i:04d}" for i in range(30)]
    sigs = {f"pkg.mod::test_base_{i}": {"same": True, "outcome": "error", "exception": ["OSError"]} for i in range(4)}
    cmp = {
        "same": 8, "same_skipped_both": 0, "regressions": [], "fixed": [], "new_tests_passing": 1,
        "new_tests_passing_ids": ["pkg.mod::test_added"], "new_tests_failing": list(ids), "new_tests_skipped": [],
        "removed_tests": [], "reparametrized": [], "skipped_missing_dependency": [], "flaky": [],
        "pr_unstable": [], "pr_unstable_noisy": [], "environment": [], "other_changes": [],
        "preexisting_failures": list(sigs), "failure_signatures": sigs, "load_failed_both": [],
        "load_failed_pr": [], "load_failed_main": [], "executed": {"main": 12, "pr": 42},
        "messages": {tid: BIND for tid in ids[:20]},
    }
    v, reason, _ = verdict_from_tests(cmp, None)
    assert v == "could_not_verify"
    assert cmp["new_tests_failing"] == []
    assert "failed to bind a local socket" in reason
    assert "verified" != v


def test_a_saved_assertion_is_not_swept_up_with_the_bind_errors():
    ids = [f"pkg.mod::test_case_{i:04d}" for i in range(5)]
    sigs = {"pkg.mod::test_base": {"same": True, "outcome": "error", "exception": ["OSError"]}}
    messages = {tid: BIND for tid in ids}
    messages[ids[0]] = ASSERTION
    cmp = {
        "same": 4, "same_skipped_both": 0, "regressions": [], "fixed": [], "new_tests_passing": 0,
        "new_tests_passing_ids": [], "new_tests_failing": list(ids), "new_tests_skipped": [],
        "removed_tests": [], "reparametrized": [], "skipped_missing_dependency": [], "flaky": [],
        "pr_unstable": [], "pr_unstable_noisy": [], "environment": [], "other_changes": [],
        "preexisting_failures": list(sigs), "failure_signatures": sigs, "load_failed_both": [],
        "load_failed_pr": [], "load_failed_main": [], "executed": {"main": 5, "pr": 10},
        "messages": messages,
    }
    v, _reason, _ = verdict_from_tests(cmp, None)
    assert v == "needs_attention"
    assert ids[0] in cmp["new_tests_failing"]
    assert ids[1] not in cmp["new_tests_failing"]


def test_saved_teardown_matches_an_untyped_base_failure():
    sigs = {"pkg.mod::test_base": {"same": True, "outcome": "error", "exception": []}}
    cmp = {
        "same": 3, "same_skipped_both": 0, "regressions": [], "fixed": [], "new_tests_passing": 0,
        "new_tests_passing_ids": [], "new_tests_failing": [NEW], "new_tests_skipped": [],
        "removed_tests": [], "reparametrized": [], "skipped_missing_dependency": [], "flaky": [],
        "pr_unstable": [], "pr_unstable_noisy": [], "environment": [], "other_changes": [],
        "preexisting_failures": list(sigs), "failure_signatures": sigs, "load_failed_both": [],
        "load_failed_pr": [], "load_failed_main": [], "executed": {"main": 4, "pr": 5},
        "messages": {NEW: TEARDOWN},
    }
    v, reason, _ = verdict_from_tests(cmp, None)
    assert v == "could_not_verify"
    assert "teardown" in reason


def test_docstring_only_does_not_upgrade_an_environment_failure():
    main = _passed({OLD: ("error", BIND)})
    pr = _passed({OLD: ("error", BIND), NEW: ("error", BIND)})
    cmp = compare_sides(_runs(main, pr))
    v, reason, _ = verdict_for(cmp, None, docstring_only=True)
    assert v == "could_not_verify"
    assert "failed to bind a local socket" in reason
    assert "hold by construction" not in reason


def _sandbox_ok() -> bool:
    return sandbox.check()[0]


@pytest.mark.skipif(not _sandbox_ok(), reason="bubblewrap cannot start here")
def test_each_run_has_a_private_loopback(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = {"HOME": str(home), "PATH": "/usr/bin:/sbin:/usr/sbin:/bin", "LANG": "C.UTF-8"}
    script = (
        "import socket\n"
        "s=socket.socket(); s.bind(('127.0.0.1', 8765)); s.listen(1); print('v4', s.getsockname()[0])\n"
        "n=socket.socket(); n.bind(('localhost', 0)); print('name', n.getsockname()[0]); n.close()\n"
        "cap=open('/proc/self/status').read().split('CapEff:')[1].split()[0]; print('cap', cap)\n"
        "import subprocess\n"
        "print(subprocess.run(['ip','link','show','lo'], capture_output=True, text=True).stdout)\n"
        "out=socket.socket(); out.settimeout(2)\n"
        "try:\n"
        "    out.connect(('1.1.1.1', 53)); print('outside-open')\n"
        "except OSError as exc:\n"
        "    print('outside', type(exc).__name__)\n"
    )
    argv, env2, _cwd = sandbox.wrap(["/usr/bin/python3", "-c", script], env, [home], network=False)
    assert "--unshare-all" in argv
    assert "--share-net" not in argv
    assert "--cap-add" in argv and "CAP_NET_ADMIN" in argv
    assert "/etc/hosts" in argv
    assert any(str(part).endswith("loopback.py") for part in argv)
    hosts = (home / ".sandbox-etc" / "hosts").read_text()
    assert "127.0.0.1 localhost" in hosts
    assert "::1 localhost" in hosts
    first = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env2)
    second = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env2)
    out1, err1 = first.communicate(timeout=30)
    out2, err2 = second.communicate(timeout=30)
    assert first.returncode == 0, err1
    assert second.returncode == 0, err2
    for out in (out1, out2):
        assert "v4 127.0.0.1" in out
        assert "name 127.0.0.1" in out
        assert "cap 0000000000000000" in out
        assert "UP" in out
        assert "outside-open" not in out
    shared = sandbox.wrap(["/bin/true"], env, [home], network=True)[0]
    assert "--share-net" in shared
    assert not any(str(part).endswith("loopback.py") for part in shared)


def test_listener_port_is_free_in_two_namespaces(tmp_path):
    """Two runs bind the same port at the same time. Each namespace has its own loopback."""
    if not _sandbox_ok():
        pytest.skip("bubblewrap cannot start here")
    script = (
        "import socket, time\n"
        "s=socket.socket(); s.bind(('localhost', 8765)); s.listen(1); print('bound', flush=True); time.sleep(0.5)\n"
    )
    procs = []
    for name in ("one", "two"):
        home = tmp_path / name
        home.mkdir()
        env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
        argv, env2, _cwd = sandbox.wrap(["/usr/bin/python3", "-c", script], env, [home], network=False)
        procs.append(subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env2))
    for proc in procs:
        out, err = proc.communicate(timeout=30)
        assert proc.returncode == 0, err
        assert "bound" in out
