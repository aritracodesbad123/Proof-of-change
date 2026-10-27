"""A hanging Chrome costs one short readiness probe per process, never the full PDF time limit."""
import os
import time

from reports import reviewer


def _fake_chrome(tmp_path, monkeypatch, script):
    fake = tmp_path / "chrome"
    fake.write_text(script)
    fake.chmod(0o755)
    monkeypatch.setattr(reviewer, "find_chrome", lambda: str(fake))
    monkeypatch.setattr(reviewer, "_CHROME_READY", {})
    return fake


def _html(tmp_path, name="r.html"):
    h = tmp_path / name
    h.write_text("<h1>Verdict: VERIFIED</h1><p>x</p><ul><li>a</li></ul>")
    return h


def test_hanging_chrome_falls_back_well_under_pdf_limit(tmp_path, monkeypatch):
    pidfile = tmp_path / "helper.pid"
    _fake_chrome(tmp_path, monkeypatch, f"#!/bin/sh\nsleep 120 &\necho $! > {pidfile}\nsleep 120\n")
    assert reviewer.PDF_TIMEOUT_S >= 60  # the real limit stays; the probe must keep us far below it
    t0 = time.monotonic()
    assert reviewer.to_pdf(str(_html(tmp_path)), str(tmp_path / "r.pdf")) is None
    first = time.monotonic() - t0
    assert first < reviewer.CHROME_PROBE_TIMEOUT_S + 8
    assert (tmp_path / "r.pdf").read_bytes().startswith(b"%PDF")
    helper = int(pidfile.read_text())
    time.sleep(0.2)
    try:
        os.kill(helper, 0)
        alive = open(f"/proc/{helper}/stat").read().split()[2] != "Z"
    except (ProcessLookupError, FileNotFoundError):
        alive = False
    assert not alive, "whole Chrome process group must be killed"
    # cached: the next PDF in this process does not wait on Chrome again
    t1 = time.monotonic()
    assert reviewer.to_pdf(str(_html(tmp_path, "s.html")), str(tmp_path / "s.pdf")) is None
    assert time.monotonic() - t1 < 3


def test_working_chrome_is_used_after_probe(tmp_path, monkeypatch):
    _fake_chrome(tmp_path, monkeypatch,
                 '#!/bin/sh\nfor a; do case "$a" in --print-to-pdf=*) printf "%%PDF-1.4 chrome" > "${a#*=}";; esac; done\n')
    calls = []
    monkeypatch.setattr(reviewer, "_fallback_pdf", lambda h, p: calls.append(p))
    assert reviewer.to_pdf(str(_html(tmp_path)), str(tmp_path / "r.pdf")) is None
    assert (tmp_path / "r.pdf").read_bytes() == b"%PDF-1.4 chrome" and not calls
    assert reviewer._CHROME_READY == {str(tmp_path / "chrome"): None}


def test_real_page_timeout_is_cached_after_probe_passed(tmp_path, monkeypatch):
    log = tmp_path / "calls.log"
    # passes the readiness probe (probe.html), hangs on any real report page
    _fake_chrome(tmp_path, monkeypatch,
                 f'#!/bin/sh\necho "$@" >> {log}\ncase "$*" in *probe.html*) '
                 'for a; do case "$a" in --print-to-pdf=*) printf "%%PDF-1.4 probe" > "${a#*=}";; esac; done;; '
                 '*) sleep 120;; esac\n')
    monkeypatch.setattr(reviewer, "PDF_TIMEOUT_S", 1)
    t0 = time.monotonic()
    assert reviewer.to_pdf(str(_html(tmp_path)), str(tmp_path / "r.pdf")) is None
    assert time.monotonic() - t0 < 8
    assert (tmp_path / "r.pdf").read_bytes().startswith(b"%PDF")
    assert "timed out" in reviewer._CHROME_READY[str(tmp_path / "chrome")]
    calls = len(log.read_text().splitlines())
    assert calls == 2  # probe + real page
    t1 = time.monotonic()
    assert reviewer.to_pdf(str(_html(tmp_path, "s.html")), str(tmp_path / "s.pdf")) is None
    assert time.monotonic() - t1 < 3
    assert len(log.read_text().splitlines()) == calls, "second PDF must not start Chrome"
