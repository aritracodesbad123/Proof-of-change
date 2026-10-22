"""Product checks fetch the Contree coverage report from a file, so the output cap cannot cut it short."""
import base64
import gzip
import hashlib
import json
import re
from types import SimpleNamespace

from tests.test_contree_only import _gate, _sides, daily_run

CAP = 65536  # Contree caps command output near this size


def _big_report():
    lines = list(range(1, 40001))
    files = {"/work/src/widget/core.py": {"executed_lines": [1, 2], "missing_lines": []}}
    for i in range(30):  # noise from other files, plus a long changed-file entry
        files[f"/work/src/widget/other{i}.py"] = {"executed_lines": lines, "missing_lines": []}
    files["/work/src/widget/core.py"]["contexts"] = {str(n): ["t" * 20] for n in lines}
    return {"meta": {}, "files": files}


class Sess:
    pr_uuid = "pr-1"

    def __init__(self, report, fail_fetch=False):
        kept = {"meta": report["meta"], "files": {k: v for k, v in report["files"].items()
                                                  if k.endswith("/widget/core.py")}}  # as _COV_PACK keeps
        raw = json.dumps(kept, separators=(",", ":")).encode()
        self.kept = kept
        self.b64 = base64.b64encode(gzip.compress(raw)).decode()
        self.fail_fetch = fail_fetch
        self.calls = []

    def run_op(self, side, shell, disposable=True, **k):
        self.calls.append(("op", disposable))
        assert "___POC_COV_START___" not in shell and "/work/poc-cov/cov.b64" in shell
        digest = hashlib.sha256(self.b64.encode()).hexdigest()
        out = f"___POC_EXIT___0\n___POC_COV_FILE___{len(self.b64)} {digest}\n___POC_LOG___\n1 passed\n"
        return {"exit_code": 0, "stdout": out[:CAP], "stderr": "", "uuid": "img-cov"}

    def run_image(self, image, shell, timeout=600):
        self.calls.append(("fetch", image))
        if self.fail_fetch:
            raise RuntimeError("contree request failed: ApiTimeoutError")
        s, e = map(int, re.search(r"cut -c (\d+)-(\d+)", shell).groups())
        return {"exit_code": 0, "stdout": self.b64[s - 1:e][:CAP] + "\n", "stderr": ""}


def _product_run(tmp_path, monkeypatch, sess, run_timeout=None):
    main_root, pr_root, item, a = _sides(tmp_path)
    a.product_check, a.pr, a.bench = True, 1, None
    if run_timeout is not None:
        a.run_timeout = run_timeout
    monkeypatch.setattr("poc.contree_sandboxes.session", lambda: sess)
    return daily_run.contree_coverage_run(item, main_root, pr_root, ["tests/test_widget.py"], tmp_path, a)


def test_large_report_is_fetched_whole(tmp_path, monkeypatch):
    report = _big_report()
    assert len(json.dumps(report)) > 20 * CAP
    sess = Sess(report)
    got = _product_run(tmp_path, monkeypatch, sess)
    assert got["status"] == "measured", got
    assert ("op", False) in sess.calls
    assert sum(1 for c in sess.calls if c[0] == "fetch") >= 1
    assert all(c[1] == "img-cov" for c in sess.calls if c[0] == "fetch")
    saved = json.loads((tmp_path / "coverage-pr.json").read_text())
    assert saved == sess.kept and len(json.dumps(saved)) > 10 * CAP


def test_report_spanning_many_pieces_is_reassembled(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_run, "COV_CHUNK", 997)
    sess = Sess(_big_report())
    got = _product_run(tmp_path, monkeypatch, sess)
    assert got["status"] == "measured", got
    assert sum(1 for c in sess.calls if c[0] == "fetch") > 3


def test_failed_fetch_stays_not_measured(tmp_path, monkeypatch):
    got = _product_run(tmp_path, monkeypatch, Sess(_big_report(), fail_fetch=True))
    assert got["status"] == "not measured"
    assert "could not be fetched from Contree" in got["why"]
    assert _gate(got)["verdict"] == "could_not_verify"


def test_checksum_mismatch_stays_not_measured(tmp_path, monkeypatch):
    sess = Sess(_big_report())
    real = sess.run_image

    def corrupt(image, shell, timeout=600):
        r = real(image, shell, timeout)
        return r | {"stdout": ("A" * (len(r["stdout"]) - 1)) + "\n"}
    sess.run_image = corrupt
    got = _product_run(tmp_path, monkeypatch, sess)
    assert got["status"] == "not measured" and "checksum" in got["why"]
    assert _gate(got)["verdict"] == "could_not_verify"


def test_no_report_file_stays_not_measured(tmp_path, monkeypatch):
    sess = Sess(_big_report())
    sess.run_op = lambda *a, **k: {"exit_code": 0, "stdout": "___POC_EXIT___1\n", "uuid": "img"}
    got = _product_run(tmp_path, monkeypatch, sess)
    assert got["status"] == "not measured" and "no report file" in got["why"]


def test_pack_script_writes_checked_file(tmp_path):
    src = tmp_path / "cov.json"
    src.write_text(json.dumps(_big_report()))
    script = daily_run._COV_PACK.replace("/work/poc-cov", str(tmp_path / "out"))
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-c", script, str(src), "widget/core.py"], capture_output=True,
                         text=True, check=True).stdout
    n, digest = re.search(r"___POC_COV_FILE___(\d+) ([0-9a-f]{64})", out).groups()
    b = (tmp_path / "out" / "cov.b64").read_text()
    assert len(b) == int(n) and hashlib.sha256(b.encode()).hexdigest() == digest
    data = json.loads(gzip.decompress(base64.b64decode(b)))
    assert list(data["files"]) == ["/work/src/widget/core.py"]


def test_study_route_unchanged(tmp_path, monkeypatch):
    main_root, pr_root, item, a = _sides(tmp_path)
    body = json.dumps({"files": {"/work/src/widget/core.py": {"executed_lines": [1, 2], "missing_lines": []}}})
    seen = {}

    def op(side, shell, disposable=True, **k):
        seen["disposable"] = disposable
        return {"exit_code": 0, "stdout": f"___POC_EXIT___0\n___POC_COV_START___\n{body}\n___POC_COV_END___\n"}
    monkeypatch.setattr("poc.contree_sandboxes.session", lambda: SimpleNamespace(pr_uuid="pr-1", run_op=op))
    got = daily_run.contree_coverage_run(item, main_root, pr_root, ["t.py"], tmp_path, a)
    assert got["status"] == "measured" and seen["disposable"] is True


def _clocked(monkeypatch, sess, per_piece):
    """Fake clock: every fetched piece takes per_piece seconds. Records the timeout given to each piece."""
    now = [0.0]
    monkeypatch.setattr(daily_run, "_cov_clock", lambda: now[0])
    real, given = sess.run_image, []

    def run_image(image, shell, timeout=600):
        given.append(timeout)
        now[0] += per_piece
        return real(image, shell, timeout)
    sess.run_image = run_image
    return given


def test_pieces_share_one_overall_deadline(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_run, "COV_CHUNK", 997)
    sess = Sess(_big_report())
    given = _clocked(monkeypatch, sess, per_piece=1)
    budget = 3600
    got = _product_run(tmp_path, monkeypatch, sess, run_timeout=budget)
    assert got["status"] == "measured", got
    assert len(given) > 3 and given[0] <= budget
    assert given == sorted(given, reverse=True) and given[-1] < given[0]
    assert all(t == budget - i for i, t in enumerate(given))


def test_running_out_of_time_stays_not_measured(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_run, "COV_CHUNK", 997)
    sess = Sess(_big_report())
    given = _clocked(monkeypatch, sess, per_piece=1000)  # far slower than the budget allows
    got = _product_run(tmp_path, monkeypatch, sess, run_timeout=3600)
    assert got["status"] == "not measured"
    assert "could not be fetched from Contree" in got["why"] and "ran out of time" in got["why"]
    assert given == [3600, 2600, 1600, 600]  # each piece gets only the time left; no piece starts past the deadline
    assert len(given) < -(-len(sess.b64) // 997)
    assert _gate(got)["verdict"] == "could_not_verify"
