"""Contree-only product checks measure probe line coverage inside Contree, or keep the cap (fail closed)."""
import base64
import gzip
import hashlib
import json
import re

from poc import probe_adequacy
from tests.test_contree_only import _sides, daily_run

REPORT = {"meta": {}, "files": {"/work/src/widget/core.py": {"executed_lines": [1, 2], "missing_lines": []}}}


def _pack(report) -> str:
    raw = report if isinstance(report, bytes) else json.dumps(report).encode()
    return base64.b64encode(gzip.compress(raw)).decode()


class Sess:
    main_uuid, pr_uuid = "main-1", "pr-1"

    def __init__(self, b64, *, digest=None, no_file=False, short=False, run_error=False, fetch_error=False):
        self.b64, self.digest = b64, digest or hashlib.sha256(b64.encode()).hexdigest()
        self.no_file, self.short, self.run_error, self.fetch_error = no_file, short, run_error, fetch_error
        self.ops = []

    def run_op(self, side, shell, disposable=True, timeout=600, files=None):
        self.ops.append((side, disposable, shell, files))
        if self.run_error:
            raise RuntimeError("contree request failed: ApiTimeoutError")
        out = "___POC_EXIT___0\n"
        if not self.no_file:
            out += f"___POC_COV_FILE___{len(self.b64)} {self.digest}\n"
        return {"exit_code": 0, "stdout": out + "___POC_LOG___\nok\n", "stderr": "", "uuid": "img-probe"}

    def run_image(self, image, shell, timeout=600):
        if self.fetch_error:
            raise RuntimeError("boom")
        s, e = map(int, re.search(r"cut -c (\d+)-(\d+)", shell).groups())
        piece = self.b64[s - 1:e]
        return {"exit_code": 0, "stdout": (piece[:-1] if self.short else piece) + "\n", "stderr": ""}


def _run(tmp_path, monkeypatch, sess, texts=None):
    main_root, pr_root, item, a = _sides(tmp_path)
    if texts:
        (main_root / "widget" / "core.py").write_text(texts[0])
        (pr_root / "widget" / "core.py").write_text(texts[1])
    probe = tmp_path / "p1.py"
    probe.write_text("print('x')\n")
    items = [{"id": "p1", "path": str(probe), "observations": []}]
    monkeypatch.setattr("poc.contree_sandboxes.session", lambda: sess)
    monkeypatch.setattr(daily_run.probes, "read_spec", lambda p: {"id": "p1", "timeout_s": 30})
    summary = daily_run.contree_probe_coverage(item, {"items": items}, main_root, pr_root, tmp_path, a)
    return items[0]["probe_changed_line_coverage"], summary


def test_success_measures_changed_lines_on_main_checkpoint(tmp_path, monkeypatch):
    sess = Sess(_pack(REPORT))
    cov, _ = _run(tmp_path, monkeypatch, sess)
    assert cov["status"] == "measured" and cov["adequacy"] == probe_adequacy.ADEQUATE
    assert cov["changed_lines_covered"] >= 1 and cov["where"] == "contree"
    side, disposable, shell, files = sess.ops[0]
    assert side == "main" and disposable is False          # saved image, so the report can be fetched
    assert "coverage run" in shell and "--include=/work/src/widget/core.py" in shell
    assert "pip install" not in shell                       # nothing installed here
    assert list(files) == ["/work/probes/p1.py"]
    assert (tmp_path / "probe-cov-p1.json").is_file()


def test_probe_that_misses_changed_lines_is_not_adequate(tmp_path, monkeypatch):
    rep = {"meta": {}, "files": {"/work/src/widget/core.py": {"executed_lines": [1], "missing_lines": [2]}}}
    cov, _ = _run(tmp_path, monkeypatch, Sess(_pack(rep)))
    assert cov["status"] == "measured" and cov["adequacy"] == probe_adequacy.NOT_ADEQUATE


def _assert_capped(cov):
    assert cov["status"] == "not measured" and cov["adequacy"] == probe_adequacy.UNMEASURED
    assert not probe_adequacy.has_measured_coverage({"probe_changed_line_coverage": cov})


def test_missing_report_keeps_cap(tmp_path, monkeypatch):
    _assert_capped(_run(tmp_path, monkeypatch, Sess(_pack(REPORT), no_file=True))[0])


def test_partial_fetch_keeps_cap(tmp_path, monkeypatch):
    _assert_capped(_run(tmp_path, monkeypatch, Sess(_pack(REPORT), short=True))[0])


def test_checksum_mismatch_keeps_cap(tmp_path, monkeypatch):
    _assert_capped(_run(tmp_path, monkeypatch, Sess(_pack(REPORT), digest="0" * 64))[0])


def test_corrupt_report_keeps_cap(tmp_path, monkeypatch):
    (tmp_path / "a").mkdir(), (tmp_path / "b").mkdir()
    _assert_capped(_run(tmp_path / "a", monkeypatch, Sess(_pack(b"{not json")))[0])
    _assert_capped(_run(tmp_path / "b", monkeypatch, Sess(base64.b64encode(b"not gzip").decode()))[0])


def test_empty_report_keeps_cap(tmp_path, monkeypatch):
    _assert_capped(_run(tmp_path, monkeypatch, Sess(_pack({"meta": {}, "files": {}})))[0])


def test_run_or_fetch_error_keeps_cap(tmp_path, monkeypatch):
    (tmp_path / "a").mkdir(), (tmp_path / "b").mkdir()
    _assert_capped(_run(tmp_path / "a", monkeypatch, Sess(_pack(REPORT), run_error=True))[0])
    _assert_capped(_run(tmp_path / "b", monkeypatch, Sess(_pack(REPORT), fetch_error=True))[0])


def test_no_session_keeps_cap(tmp_path, monkeypatch):
    _assert_capped(_run(tmp_path, monkeypatch, None)[0])


def test_study_route_does_not_call_probe_coverage():
    src = open(daily_run.__file__).read()
    block = src.split("if measure_coverage:  # product route: each probe runs", 1)[1].split("settle_probes(rec)", 1)[0]
    assert "Contree-only check: probe coverage needs a local side" in block  # non-product branch unchanged


SECRET = "ghp_" + "A" * 36


def test_read_spec_any_error_keeps_cap_and_logs_redacted(tmp_path, monkeypatch):
    main_root, pr_root, item, a = _sides(tmp_path)
    probe = tmp_path / "p1.py"
    probe.write_text("print('x')\n")
    items = [{"id": "p1", "path": str(probe), "observations": []}]
    sess = Sess(_pack(REPORT))
    monkeypatch.setattr("poc.contree_sandboxes.session", lambda: sess)

    def boom(p):
        raise ValueError(f"bad spec token={SECRET}")
    monkeypatch.setattr(daily_run.probes, "read_spec", boom)
    daily_run.contree_probe_coverage(item, {"items": items}, main_root, pr_root, tmp_path, a)
    _assert_capped(items[0]["probe_changed_line_coverage"])
    assert sess.ops == []                                   # nothing ran for that probe
    log = (tmp_path / "probe-coverage.log").read_text()
    assert "ValueError" in log and SECRET not in log


def test_report_write_error_keeps_cap_and_logs_redacted(tmp_path, monkeypatch):
    real = daily_run.Path.write_text

    def flaky(self, data, *k, **kw):
        if self.name == "probe-cov-p1.json":
            raise OSError(f"disk full token={SECRET}")
        return real(self, data, *k, **kw)
    monkeypatch.setattr(daily_run.Path, "write_text", flaky)
    cov, _ = _run(tmp_path, monkeypatch, Sess(_pack(REPORT)))
    _assert_capped(cov)
    log = (tmp_path / "probe-coverage.log").read_text()
    assert "OSError" in log and SECRET not in log


def test_log_write_error_keeps_cap_and_does_not_crash(tmp_path, monkeypatch, capsys):
    real = daily_run.Path.write_text

    def flaky(self, data, *k, **kw):
        if self.name == "probe-coverage.log":
            raise OSError(f"read-only token={SECRET}")
        return real(self, data, *k, **kw)
    monkeypatch.setattr(daily_run.Path, "write_text", flaky)
    cov, summary = _run(tmp_path, monkeypatch, Sess(_pack(REPORT)))
    _assert_capped(cov)
    assert SECRET not in capsys.readouterr().out and SECRET not in json.dumps(cov)


MAIN_SRC = "def f():\n    a = 1\n    return a\ndef g():\n    return 1\n"
PR_SRC = "def f():\n    a = 1\n    b = 2\n    c = 3\n    return a\ndef g():\n    return 2\n"


def test_changed_lines_use_main_side_numbering(tmp_path, monkeypatch):
    # The PR inserts two lines in f() and replaces g()'s return, so that line is 5 on main but 7 on the PR.
    assert probe_adequacy.main_side_lines(MAIN_SRC, PR_SRC) == {2, 3, 5}
    f = "/work/src/widget/core.py"
    (tmp_path / "a").mkdir(), (tmp_path / "b").mkdir()
    main_hit = {"meta": {}, "files": {f: {"executed_lines": [4, 5], "missing_lines": [1, 2, 3]}}}
    cov, _ = _run(tmp_path / "a", monkeypatch, Sess(_pack(main_hit)), (MAIN_SRC, PR_SRC))
    assert cov["changed_lines_total"] == 3 and cov["changed_lines_covered"] == 1   # main line 5 counted
    # a report that only has the PR-side number (7) for g()'s return must not count as covering the change
    pr_numbered = {"meta": {}, "files": {f: {"executed_lines": [6, 7], "missing_lines": [1, 2, 3, 4, 5]}}}
    cov, _ = _run(tmp_path / "b", monkeypatch, Sess(_pack(pr_numbered)), (MAIN_SRC, PR_SRC))
    assert cov["changed_lines_covered"] == 0 and cov["adequacy"] == probe_adequacy.NOT_ADEQUATE
