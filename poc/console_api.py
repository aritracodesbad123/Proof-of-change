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


def list_runs(limit: int = 50) -> list[dict]:
    rows: list[tuple[float, dict]] = []
    if not RUNS_ROOT.is_dir():
        return []
    for path in RUNS_ROOT.rglob("record.json"):
        try:
            rec = json.loads(path.read_text())
            mtime = path.stat().st_mtime
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("record_kind") and rec.get("record_kind") != "pr_run":
            continue
        rid = rec.get("id") or path.parent.name
        pr = rec.get("pr") if isinstance(rec.get("pr"), dict) else {}
        rows.append((mtime, {
            "id": rid,
            "repo": rec.get("repo"),
            "pr": pr.get("number"),
            "url": pr.get("url"),
            "title": (pr.get("title") or rec.get("title")),
            "verdict": rec.get("verdict"),
            "reason": (rec.get("reason") or "")[:240],
            "tested_at_ist": rec.get("tested_at_ist") or rec.get("date_ist"),
            "machine": rec.get("machine") or "local",
            "path": str(path.relative_to(REPO_ROOT)),
            "folder": str(path.parent.relative_to(REPO_ROOT)),
        }))
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
            hosted = HOSTED / f"{rec.get('id') or run_id}.html"
            return {
                "record": rec,
                "path": str(path.relative_to(REPO_ROOT)),
                "folder": str(path.parent.relative_to(REPO_ROOT)),
                "hosted_report": str(hosted.relative_to(REPO_ROOT)) if hosted.is_file() else None,
            }
    return None


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
            tail = ((p.stdout or "") + "\n" + (p.stderr or ""))[-4000:]
            os.environ["POC_PROGRESS_PATH"] = str(progress_path)
            if p.returncode == 0:
                rp.emit("done", detail="check finished")
            else:
                rp.emit("failed", detail=f"exit {p.returncode}")
            with _jobs_lock:
                job["exit"] = p.returncode
                job["log_tail"] = tail
                job["status"] = "done" if p.returncode == 0 else "failed"
                job["finished_at"] = time.time()
            for row in list_runs(20):
                if row.get("repo") == m.group(1) and row.get("pr") == int(m.group(2)):
                    with _jobs_lock:
                        job["run_id"] = row["id"]
                    break
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
                "build": "sandbox-fallback-v3",
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
