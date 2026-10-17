"""Local JSON API for the Proof-of-Change operator console (browse runs + start checks).

    python -m poc.console_api --port 8787

Endpoints:
  GET  /api/health
  GET  /api/runs
  GET  /api/runs/<id>
  POST /api/checks   JSON {"pr_url": "https://github.com/o/r/pull/N"}
  GET  /api/jobs/<job_id>

Serves console/web/dist when built. CORS open for local Vite (5173).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_ROOT = Path(os.environ.get("POC_OPS_RUNS", REPO_ROOT / "ops" / "runs"))
HOSTED = REPO_ROOT / "reports" / "hosted"
WEB_DIST = REPO_ROOT / "console" / "web" / "dist"
PR_RE = re.compile(r"https?://github\.com/([^/]+/[^/]+)/pull/(\d+)", re.I)

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
# ponytail: Render free disk is wiped on sleep/redeploy; keep last finished runs in RAM for this process.
_recent_runs: dict[str, dict[str, Any]] = {}
_RECENT_MAX = 30
_RUN_LOG_RE = re.compile(r"run log:\s*(\S+/ops/runs/[^/\s]+)/REPORT\.md")


def contree_usable() -> bool:
    """True only when Contree can actually start (creds + SDK). Env alone is not enough."""
    if not (os.environ.get("NEBIUS_API_KEY") and os.environ.get("NEBIUS_PROJECT_ID")):
        return False
    try:
        import contree_sdk  # noqa: F401
    except ImportError:
        return False
    return True


def console_run_flags() -> tuple[list[str], str | None]:
    """Extra daily_run flags for hosted console (Render blocks bwrap uid maps).

    Prefer Contree when it can actually run. Otherwise, if bubblewrap cannot start here,
    pass --unsafe-no-sandbox so a public-PR demo can still run (recorded in the job note).
    Set POC_UNSAFE_NO_SANDBOX=0 to refuse instead of falling back.
    """
    if contree_usable():
        # Contree is remote; also disable the local bwrap gate (Render blocks uid maps).
        # If Contree checkpoints fail mid-run, daily_run falls back to local — unsafe keeps that path alive.
        return (["--sandbox-backend", "contree", "--unsafe-no-sandbox"],
                "using Contree sandboxes (local bwrap skipped)")
    refuse = (os.environ.get("POC_UNSAFE_NO_SANDBOX") or "").strip().lower() in ("0", "false", "no")
    force = (os.environ.get("POC_UNSAFE_NO_SANDBOX") or "").strip().lower() in ("1", "true", "yes")
    ok = False
    why = "sandbox check skipped"
    try:
        from guardrails import sandbox
        ok, why = sandbox.check()
    except Exception as e:  # noqa: BLE001
        ok, why = False, f"{type(e).__name__}: {e}"
    if ok and not force:
        return [], None
    if refuse:
        return [], (
            f"sandbox unavailable ({why}); install contree-sdk + NEBIUS_PROJECT_ID, "
            "or set POC_UNSAFE_NO_SANDBOX=1"
        )
    # ponytail: auto unsafe on PaaS without working Contree/bwrap — console motif requires a runnable path
    return ["--unsafe-no-sandbox"], f"sandbox unavailable ({why}); running with --unsafe-no-sandbox"


def _row_from_record(rec: dict, path: Path | None = None) -> dict:
    rid = rec.get("id") or (path.parent.name if path else "unknown")
    pr = rec.get("pr") if isinstance(rec.get("pr"), dict) else {}
    folder = str(path.parent.relative_to(REPO_ROOT)) if path else f"(memory)/{rid}"
    return {
        "id": rid,
        "repo": rec.get("repo"),
        "pr": pr.get("number"),
        "url": pr.get("url"),
        "title": (pr.get("title") or rec.get("title")),
        "verdict": rec.get("verdict"),
        "reason": (rec.get("reason") or "")[:240],
        "tested_at_ist": rec.get("tested_at_ist") or rec.get("date_ist"),
        "machine": rec.get("machine") or "local",
        "path": str(path.relative_to(REPO_ROOT)) if path else None,
        "folder": folder,
        "source": "disk" if path else "memory",
    }


def remember_run(rec: dict, path: Path | None = None) -> dict:
    """Keep a finished PR record in RAM so the console still lists it after Render wipes disk."""
    row = _row_from_record(rec, path)
    rid = row["id"]
    hosted = HOSTED / f"{rid}.html"
    snap = {
        "row": row,
        "record": rec,
        "folder": row["folder"],
        "hosted_report": str(hosted.relative_to(REPO_ROOT)) if hosted.is_file() else None,
        "saved_at": time.time(),
    }
    with _jobs_lock:
        _recent_runs[rid] = snap
        while len(_recent_runs) > _RECENT_MAX:
            oldest = min(_recent_runs.items(), key=lambda kv: kv[1].get("saved_at") or 0)
            _recent_runs.pop(oldest[0], None)
    return row


def list_runs(limit: int = 50) -> list[dict]:
    rows: list[tuple[float, dict]] = []
    seen: set[str] = set()
    if RUNS_ROOT.is_dir():
        for path in RUNS_ROOT.rglob("record.json"):
            try:
                rec = json.loads(path.read_text())
                mtime = path.stat().st_mtime
            except (OSError, json.JSONDecodeError):
                continue
            if rec.get("record_kind") and rec.get("record_kind") != "pr_run":
                continue
            row = _row_from_record(rec, path)
            seen.add(row["id"])
            rows.append((mtime, row))
            remember_run(rec, path)
    with _jobs_lock:
        mem = list(_recent_runs.values())
    for snap in mem:
        row = snap["row"]
        if row["id"] in seen:
            continue
        rows.append((float(snap.get("saved_at") or 0), row))
    rows.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in rows[:limit]]


def get_run(run_id: str) -> dict | None:
    run_id = unquote(run_id)
    for path in RUNS_ROOT.rglob("record.json") if RUNS_ROOT.is_dir() else []:
        try:
            rec = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("id") == run_id or path.parent.name == run_id:
            remember_run(rec, path)
            hosted = HOSTED / f"{rec.get('id') or run_id}.html"
            return {
                "record": rec,
                "path": str(path.relative_to(REPO_ROOT)),
                "folder": str(path.parent.relative_to(REPO_ROOT)),
                "hosted_report": str(hosted.relative_to(REPO_ROOT)) if hosted.is_file() else None,
            }
    with _jobs_lock:
        snap = _recent_runs.get(run_id)
    if snap:
        return {
            "record": snap["record"],
            "path": snap["row"].get("path"),
            "folder": snap["folder"],
            "hosted_report": snap.get("hosted_report"),
            "source": "memory",
        }
    return None


def job_log_and_error(stdout: str, stderr: str, returncode: int) -> tuple[str, str | None]:
    """Build a useful log tail; prefer stderr / Stopped lines when the process failed."""
    out, err = (stdout or "").strip(), (stderr or "").strip()
    parts: list[str] = []
    if returncode and err:
        parts.append("--- stderr ---\n" + err[-3500:])
    if out:
        parts.append("--- stdout ---\n" + out[-3500:])
    elif err and not parts:
        parts.append(err[-4000:])
    tail = "\n\n".join(parts)[-6000:]
    reason = None
    for line in (err + "\n" + out).splitlines():
        s = line.strip()
        if s.startswith("Stopped:") or "PR selection failed" in s or "harness error" in s:
            reason = s
    m = _RUN_LOG_RE.search(out + "\n" + err)
    if m:
        meta_path = Path(m.group(1)) / "run_meta.json"
        try:
            meta = json.loads(meta_path.read_text())
            probs = meta.get("problems") or []
            if probs and not reason:
                reason = "; ".join(str(p) for p in probs[:5])
        except (OSError, json.JSONDecodeError):
            pass
    if returncode and not reason:
        reason = f"check exited {returncode} (see log tail)"
    return tail, reason


def find_record_for_pr(repo: str, pr: int) -> tuple[dict, Path] | None:
    """Newest matching pr_run record on disk for this repo/PR."""
    best: tuple[float, dict, Path] | None = None
    if not RUNS_ROOT.is_dir():
        return None
    for path in RUNS_ROOT.rglob("record.json"):
        try:
            rec = json.loads(path.read_text())
            mtime = path.stat().st_mtime
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("record_kind") and rec.get("record_kind") != "pr_run":
            continue
        if rec.get("repo") != repo:
            continue
        prd = rec.get("pr") if isinstance(rec.get("pr"), dict) else {}
        if prd.get("number") != pr:
            continue
        if best is None or mtime > best[0]:
            best = (mtime, rec, path)
    if not best:
        return None
    return best[1], best[2]


def start_check(pr_url: str, *, model_provider: str = "nebius") -> dict:
    from poc import run_progress

    m = PR_RE.search(pr_url.strip())
    if not m:
        raise ValueError("pr_url must look like https://github.com/owner/repo/pull/123")
    job_id = uuid.uuid4().hex[:12]
    progress_path = REPO_ROOT / "ops" / "runs" / "_jobs" / f"{job_id}.jsonl"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    if progress_path.exists():
        progress_path.unlink()
    job = {
        "id": job_id,
        "status": "queued",
        "pr_url": pr_url.strip(),
        "repo": m.group(1),
        "pr": int(m.group(2)),
        "started_at": None,
        "finished_at": None,
        "exit": None,
        "error": None,
        "run_id": None,
        "log_tail": "",
        "progress_path": str(progress_path),
        "stages": [],
        "current_stage": "queued",
        "current_agent": None,
        "current_detail": None,
        "swarm": {"ultra": "idle", "lightning": "idle", "super": "idle"},
    }
    with _jobs_lock:
        _jobs[job_id] = job
    # Seed progress file so UI shows queued before the child starts.
    prev = os.environ.get("POC_PROGRESS_PATH")
    os.environ["POC_PROGRESS_PATH"] = str(progress_path)
    try:
        run_progress.emit("queued", detail=f"{m.group(1)}#{m.group(2)}")
    finally:
        if prev is None:
            os.environ.pop("POC_PROGRESS_PATH", None)
        else:
            os.environ["POC_PROGRESS_PATH"] = prev

    def work():
        from poc import run_progress as rp

        env = os.environ.copy()
        env["POC_PROGRESS_PATH"] = str(progress_path)
        with _jobs_lock:
            job["status"] = "running"
            job["started_at"] = time.time()
        os.environ["POC_PROGRESS_PATH"] = str(progress_path)
        rp.emit("fetch_pr", detail="loading pull request")
        flags, note = console_run_flags()
        if note:
            rp.emit("fetch_pr", detail=note[:200])
        argv = [str(REPO_ROOT / ".venv" / "bin" / "python"), str(REPO_ROOT / "ops" / "daily_run.py"),
                "--pr", pr_url.strip(), "--model-provider", model_provider, *flags]
        if not (REPO_ROOT / ".venv" / "bin" / "python").is_file():
            argv[0] = os.environ.get("PYTHON", "python3")
        try:
            # ponytail: one check at a time in-process thread; job queue if operators run many in parallel
            p = subprocess.run(argv, cwd=str(REPO_ROOT), capture_output=True, text=True,
                               timeout=None, env=env)
            tail, fail_reason = job_log_and_error(p.stdout or "", p.stderr or "", p.returncode)
            os.environ["POC_PROGRESS_PATH"] = str(progress_path)
            found = find_record_for_pr(m.group(1), int(m.group(2)))
            # A written record means the check produced analysis — surface it even if exit!=0 (problems list).
            ok = p.returncode == 0 or found is not None
            if ok:
                rp.emit("done", detail="check finished" if p.returncode == 0 else "finished with problems")
            else:
                rp.emit("failed", detail=(fail_reason or f"exit {p.returncode}")[:200])
            with _jobs_lock:
                job["exit"] = p.returncode
                job["log_tail"] = tail
                job["status"] = "done" if ok else "failed"
                job["finished_at"] = time.time()
                if fail_reason and not ok:
                    job["error"] = fail_reason
                elif fail_reason and p.returncode != 0:
                    job["warning"] = fail_reason
                if found:
                    rec, path = found
                    row = remember_run(rec, path)
                    job["run_id"] = row["id"]
                    job["record"] = rec
                    job["folder"] = row["folder"]
        except Exception as e:  # noqa: BLE001
            os.environ["POC_PROGRESS_PATH"] = str(progress_path)
            rp.emit("failed", detail=f"{type(e).__name__}: {e}"[:200])
            with _jobs_lock:
                job["status"] = "failed"
                job["error"] = f"{type(e).__name__}: {e}"
                job["finished_at"] = time.time()

    threading.Thread(target=work, daemon=True).start()
    return _job_public(job)


def _job_public(job: dict) -> dict:
    from poc import run_progress

    out = dict(job)
    prog = run_progress.job_progress(job.get("progress_path"))
    out.update(prog)
    out.pop("progress_path", None)
    return out


def get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        j = _jobs.get(job_id)
        if not j:
            return None
        return _job_public(j)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, obj: Any):
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, content_type: str):
        data = path.read_bytes()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/api/health":
            flags, note = console_run_flags()
            return self._json(200, {
                "ok": True,
                "service": "proof-of-change-console",
                "build": "sandbox-fallback-v4",
                "has_git": (REPO_ROOT / ".git").is_dir(),
                "poc_commit_env": bool(
                    (os.environ.get("POC_COMMIT") or os.environ.get("RENDER_GIT_COMMIT") or "").strip()),
                "contree_ready": contree_usable(),
                "run_flags": flags,
                "run_note": note,
            })
        if path == "/api/runs":
            return self._json(200, {"runs": list_runs()})
        if path.startswith("/api/runs/"):
            rid = path[len("/api/runs/"):]
            got = get_run(rid)
            if not got:
                return self._json(404, {"error": "not found"})
            return self._json(200, got)
        if path.startswith("/api/jobs/"):
            jid = path[len("/api/jobs/"):]
            job = get_job(jid)
            if not job:
                return self._json(404, {"error": "not found"})
            return self._json(200, job)

        # static SPA
        if WEB_DIST.is_dir():
            rel = path.lstrip("/") or "index.html"
            cand = (WEB_DIST / rel).resolve()
            if not str(cand).startswith(str(WEB_DIST.resolve())):
                return self._json(400, {"error": "bad path"})
            if cand.is_file():
                ctype = "text/html" if cand.suffix == ".html" else (
                    "application/javascript" if cand.suffix in (".js", ".mjs") else
                    "text/css" if cand.suffix == ".css" else "application/octet-stream")
                return self._file(cand, ctype)
            index = WEB_DIST / "index.html"
            if index.is_file() and not path.startswith("/api"):
                return self._file(index, "text/html")
        return self._json(404, {"error": "not found", "hint": "build console/web (npm run build) or use Vite on :5173"})

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "bad json"})
        if path == "/api/checks":
            pr_url = (body.get("pr_url") or "").strip()
            provider = (body.get("model_provider") or "nebius").strip() or "nebius"
            try:
                job = start_check(pr_url, model_provider=provider)
            except ValueError as e:
                return self._json(400, {"error": str(e)})
            return self._json(202, job)
        return self._json(404, {"error": "not found"})


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Proof-of-Change console API http://{host}:{port}  (UI: Vite :5173 or {WEB_DIST})", flush=True)
    httpd.serve_forever()


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Proof-of-Change operator console API")
    ap.add_argument("--host", default=os.environ.get("POC_CONSOLE_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("POC_CONSOLE_PORT", "8787")))
    a = ap.parse_args(argv)
    serve(a.host, a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
