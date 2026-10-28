"""GitHub App surface for Proof-of-Change (REQUIREMENTS §4 steps 0/10).

Posts only to allowlisted demo/mirror repos (G-ext). Never blocks merges: check runs are
neutral/success advice only. Local HTML reports stay the offline path.

Wire a real App: set GITHUB_APP_INSTALLATION_TOKEN (or App JWT env) + GITHUB_WEBHOOK_SECRET and
POC_DEMO_REPOS=owner/repo,... then: python -m poc.github_app

POST /webhook checks the signature, skips a delivery ID it has seen (kept under the state dir), queues the
check and replies 202. One worker runs one check at a time; on a hosted deploy each check counts toward
POC_DAILY_CAP through the console's own counter.
"""
from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import queue
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable

DEMO_REPOS_ENV = "POC_DEMO_REPOS"
REPORT_BASE_ENV = "POC_REPORT_BASE_URL"
TOKEN_ENV = "GITHUB_APP_INSTALLATION_TOKEN"
WEBHOOK_SECRET_ENV = "GITHUB_WEBHOOK_SECRET"
API = "https://api.github.com"
PROVE_RE = re.compile(r"^/prove(?:\s+(.+))?$", re.I | re.M)
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HOSTED = REPO_ROOT / "reports" / "hosted"
HOSTED_REPORTS_ENV = "POC_HOSTED_REPORTS_DIR"
OPS_RUNS_ENV = "POC_OPS_RUNS"


def hosted_reports_dir(env: dict | None = None) -> Path:
    """Where hosted HTML reports are written and read: POC_HOSTED_REPORTS_DIR, else reports/hosted in the repo.

    The console reads the same setting, so a deploy can keep the app code read-only."""
    env = os.environ if env is None else env
    raw = (env.get(HOSTED_REPORTS_ENV) or "").strip()
    return Path(raw) if raw else DEFAULT_HOSTED


def ops_runs_dir(env: dict | None = None) -> Path:
    """Run folders: POC_OPS_RUNS (the console's setting), else ops/runs in the repo."""
    env = os.environ if env is None else env
    raw = (env.get(OPS_RUNS_ENV) or "").strip()
    return Path(raw) if raw else REPO_ROOT / "ops" / "runs"


class GitHubAppError(RuntimeError):
    """Safe error for App/post failures; never include tokens or PEM material."""


def demo_repos(env: dict | None = None) -> set[str]:
    env = os.environ if env is None else env
    raw = env.get(DEMO_REPOS_ENV) or ""
    return {r.strip().lower() for r in raw.split(",") if r.strip()}


def may_post(repo: str, env: dict | None = None) -> bool:
    """G-ext: write only to allowlisted demo/mirror repos."""
    return repo.lower() in demo_repos(env)


def verify_webhook(body: bytes, signature: str | None, secret: str | None) -> bool:
    if not secret or not signature:
        return False
    sig = signature.removeprefix("sha256=")
    dig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(dig, sig)


def parse_prove(comment_body: str) -> str | None:
    """Return optional claim text from a /prove comment, or None if not a prove command."""
    m = PROVE_RE.search(comment_body or "")
    if not m:
        return None
    claim = (m.group(1) or "").strip().strip('"').strip("'")
    return claim or ""


def check_run_payload(repo: str, head_sha: str, verdict: str, summary: str, report_url: str | None = None,
                      env: dict | None = None) -> dict:
    """GitHub check-run body. Conclusion is always success/neutral — never failure (non-blocking)."""
    if not may_post(repo, env):
        raise PermissionError(f"refusing to post check run on non-demo repo {repo!r}")
    conclusion = "neutral" if verdict != "verified" else "success"
    body = {
        "name": "Proof-of-Change",
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": conclusion,
        "output": {
            "title": f"Proof-of-Change: {verdict}",
            "summary": (summary or "")[:65000],
        },
    }
    if report_url:
        body["details_url"] = report_url
    return body


def summary_comment(verdict: str, reason: str, report_url: str | None = None) -> str:
    lines = [f"**Proof-of-Change:** `{verdict}`", "", reason or "(no reason)", ""]
    if report_url:
        lines.append(f"[Full report]({report_url})")
    lines.append("_Advice only — this never blocks a merge._")
    return "\n".join(lines)


def handle_event(event: str, payload: dict, env: dict | None = None) -> dict:
    """Dispatcher: returns an action plan; does not call GitHub until apply()."""
    env = os.environ if env is None else env
    repo = ((payload.get("repository") or {}).get("full_name") or "")
    if event == "issue_comment" and payload.get("action") == "created":
        body = ((payload.get("comment") or {}).get("body") or "")
        claim = parse_prove(body)
        if claim is None:
            return {"action": "ignore", "why": "not a /prove comment"}
        issue = payload.get("issue") or {}
        # A comment on a plain issue is not a pull request. GitHub includes
        # issue.pull_request only when the comment is on a pull request.
        if not isinstance(issue.get("pull_request"), dict):
            return {"action": "ignore", "why": "a /prove comment on an issue is ignored; comment on the pull request"}
        if not may_post(repo, env):
            return {"action": "refuse", "why": f"repo {repo} not in {DEMO_REPOS_ENV}"}
        return {"action": "prove", "repo": repo, "claim": claim, "pr": issue.get("number")}
    if event == "pull_request" and payload.get("action") in ("opened", "synchronize", "reopened"):
        if not may_post(repo, env):
            return {"action": "refuse", "why": f"repo {repo} not in {DEMO_REPOS_ENV}"}
        pr = (payload.get("pull_request") or {})
        return {"action": "run", "repo": repo, "event": event,
                "pr": (pr.get("number") or (payload.get("number"))),
                "head_sha": (pr.get("head") or {}).get("sha")}
    if event == "check_suite" and payload.get("action") in ("requested", "rerequested"):
        if not may_post(repo, env):
            return {"action": "refuse", "why": f"repo {repo} not in {DEMO_REPOS_ENV}"}
        suite = payload.get("check_suite") or {}
        prs = suite.get("pull_requests") or []
        pr_n = prs[0].get("number") if prs else None
        return {"action": "run", "repo": repo, "event": event, "pr": pr_n,
                "head_sha": suite.get("head_sha")}
    return {"action": "ignore", "why": f"unhandled event {event}"}


def _pem(env: dict) -> str | None:
    raw = env.get("GITHUB_APP_PRIVATE_KEY")
    if not raw:
        return None
    p = Path(raw)
    if p.is_file():
        return p.read_text()
    return raw.replace("\\n", "\n")


def installation_token(env: dict | None = None) -> str | None:
    """Installation token from GITHUB_APP_INSTALLATION_TOKEN, or mint via App JWT (needs PyJWT)."""
    env = os.environ if env is None else env
    tok = (env.get(TOKEN_ENV) or "").strip()
    if tok:
        return tok
    app_id = (env.get("GITHUB_APP_ID") or "").strip()
    inst = (env.get("GITHUB_APP_INSTALLATION_ID") or "").strip()
    pem = _pem(env)
    if not (app_id and inst and pem):
        return None
    try:
        import jwt  # PyJWT
    except ImportError as e:
        raise GitHubAppError(
            "GITHUB_APP_ID/PRIVATE_KEY set but PyJWT is missing; "
            "pip install -e '.[github]' or set GITHUB_APP_INSTALLATION_TOKEN"
        ) from e
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 9 * 60, "iss": app_id}
    try:
        encoded = jwt.encode(payload, pem, algorithm="RS256")
    except Exception as e:  # noqa: BLE001
        raise GitHubAppError(f"App JWT mint failed: {type(e).__name__}") from None
    if isinstance(encoded, bytes):
        encoded = encoded.decode()
    url = f"{API}/app/installations/{inst}/access_tokens"
    raw = _http_json("POST", url, token=None, body={}, extra_headers={
        "Authorization": f"Bearer {encoded}",
        "Accept": "application/vnd.github+json",
    })
    token = (raw or {}).get("token")
    if not token:
        raise GitHubAppError("installation token response had no token field")
    return str(token)


def _http_json(method: str, url: str, *, token: str | None, body: dict | None = None,
               extra_headers: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "proof-of-change",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raise GitHubAppError(f"GitHub API {method} failed: HTTP {e.code}") from None
    except urllib.error.URLError as e:
        raise GitHubAppError(f"GitHub API {method} failed: {type(e.reason).__name__}") from None


def post_check_run(repo: str, payload: dict, token: str, env: dict | None = None) -> dict:
    if not may_post(repo, env):
        raise PermissionError(f"refusing to post check run on non-demo repo {repo!r}")
    # br-allow-external: G-ext demo-repo check runs only (may_post); never upstream
    return _http_json("POST", f"{API}/repos/{repo}/check-runs", token=token, body=payload)


def post_pr_comment(repo: str, pr: int, body: str, token: str, env: dict | None = None) -> dict:
    if not may_post(repo, env):
        raise PermissionError(f"refusing to post comment on non-demo repo {repo!r}")
    # br-allow-external: G-ext demo-repo PR comments only (may_post); never upstream
    return _http_json("POST", f"{API}/repos/{repo}/issues/{int(pr)}/comments", token=token,
                      body={"body": body})


def report_url_for(path: Path, env: dict | None = None) -> str | None:
    env = os.environ if env is None else env
    base = (env.get(REPORT_BASE_ENV) or "").rstrip("/")
    if not base:
        return None
    return f"{base}/{path.name}"


def write_hosted_report(rec: dict, out_dir: Path | None = None) -> Path:
    """Static behavior-map HTML for one PR record (hosted or opened locally)."""
    out_dir = Path(out_dir) if out_dir is not None else hosted_reports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    rid = rec.get("id") or "run"
    path = out_dir / f"{rid}.html"
    claims = rec.get("behaviour_claims") or []
    probes = ((rec.get("probes") or {}).get("items") or [])
    agents = rec.get("agents") or {}
    rows_c = "".join(
        f"<tr><td>{c.get('id','')}</td><td>{_esc(c.get('text') or c.get('claim') or '')}</td>"
        f"<td>{_esc(c.get('status') or '')}</td></tr>" for c in claims)
    rows_p = "".join(
        f"<tr><td>{_esc(p.get('id'))}</td><td>{_esc(p.get('about'))}</td>"
        f"<td>{_esc(', '.join(p.get('labels') or []))}</td></tr>" for p in probes[:40])
    expl = (rec.get("explanation") or {}).get("text") or ""
    from poc import related_reports
    background = rec.get("related_reports") if isinstance(rec.get("related_reports"), dict) else None
    background_text = str((background or {}).get("text") or "").strip()
    background_html = ""
    if background_text:
        background_html = (
            f"<h2>{_esc(related_reports.REPORT_LABEL)}</h2><p>{_esc(background_text)}</p>"
        )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Proof-of-Change {_esc(rid)}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;max-width:960px;line-height:1.45}}
.banner{{padding:1rem;border-radius:8px;background:#f0f4f8}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #ccc;padding:.4rem;text-align:left}}
.meta{{color:#555;font-size:.9rem}}
</style></head><body>
<h1>Proof-of-Change</h1>
<div class="banner"><strong>{_esc(rec.get('verdict'))}</strong> — {_esc(rec.get('reason'))}</div>
<p class="meta">Repo {_esc(rec.get('repo'))} · machine {_esc(rec.get('machine') or 'local')} ·
sandbox {_esc(rec.get('sandbox_backend') or 'local')}</p>
<h2>Behavior map</h2>
<p>Claims → probes. Model labels are advisory; code owns the verdict.</p>
<h3>Claims</h3>
<table><tr><th>Id</th><th>Claim</th><th>Status</th></tr>{rows_c or '<tr><td colspan=3>none</td></tr>'}</table>
<h3>Probes</h3>
<table><tr><th>Id</th><th>About</th><th>Labels</th></tr>{rows_p or '<tr><td colspan=3>none</td></tr>'}</table>
<h2>Summary</h2>
<p>{_esc(expl) or '(no model summary)'}</p>
<p class="meta">Agents: {_esc(json.dumps(agents.get('roles') or agents.get('status') or 'none'))}</p>
{background_html}
</body></html>"""
    path.write_text(html)
    return path


def _load_latest_record(repo: str, pr: int, env: dict | None = None) -> dict | None:
    """Best-effort: newest record.json under the run folders (POC_OPS_RUNS, else ops/runs) matching this PR."""
    runs = ops_runs_dir(env)
    if not runs.is_dir():
        return None
    needle = f"-{pr}"
    repo_slug = repo.replace("/", "-")
    candidates: list[Path] = []
    for rec_path in runs.rglob("record.json"):
        try:
            rec = json.loads(rec_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("repo") == repo and (rec.get("pr") or {}).get("number") == pr:
            candidates.append(rec_path)
        elif repo_slug in rec_path.parent.name and needle in rec_path.parent.name:
            candidates.append(rec_path)
    if not candidates:
        return None
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    return json.loads(newest.read_text())


CONTREE_FLAGS = ("--sandbox-backend", "contree", "--require-contree")


def check_argv(pr_url: str, env: dict | None = None) -> list[str]:
    """Arguments for one product check started by the GitHub App.

    ``--related-reports`` is quoted background for the advisory AI. ``--swarm`` turns the
    advisory swarm on for every App check. A study run uses neither. The App does not set
    ``POC_SWARM`` in the environment, so nothing else in the process is turned on.
    Pull-request code runs only in Contree: ``--require-contree`` stops the check with
    'Contree unavailable' (could not verify) instead of falling back to local bubblewrap.
    """
    env = os.environ if env is None else env
    from poc import related_reports
    provider = env.get("POC_MODEL_PROVIDER") or "nebius"
    # Same as the console: run folders and reviewer reports go where POC_OPS_DIR / POC_REPORT_DIR say.
    extra: list[str] = []
    ops_dir = (env.get("POC_OPS_DIR") or "").strip()
    if ops_dir:
        extra.extend(["--ops-dir", ops_dir])
    report_dir = (env.get("POC_REPORT_DIR") or "").strip()
    if report_dir:
        extra.extend(["--report-dir", report_dir])
    return ["--pr", pr_url, "--model-provider", provider, "--swarm", *related_reports.product_flags(),
            *CONTREE_FLAGS, *extra]


def apply(plan: dict, *, dry_run: bool | None = None, env: dict | None = None,
          runner: Callable[..., int] | None = None, hosted_dir: Path | None = None) -> dict[str, Any]:
    """Execute a handle_event plan: run daily_run for the PR, write hosted HTML, post check+comment if token."""
    env = os.environ if env is None else env
    action = plan.get("action")
    if action in ("ignore", "refuse"):
        return {"ok": True, **plan}
    if action not in ("prove", "run"):
        return {"ok": False, "error": f"unknown action {action!r}", "plan": plan}
    repo = plan.get("repo")
    pr = plan.get("pr")
    if not repo or not pr:
        return {"ok": False, "error": "plan needs repo and pr", "plan": plan}
    if not may_post(str(repo), env):
        return {"ok": False, "action": "refuse", "why": f"repo {repo} not in {DEMO_REPOS_ENV}"}

    token = None
    try:
        token = installation_token(env)
    except GitHubAppError as e:
        return {"ok": False, "error": str(e), "plan": plan}
    force_dry = dry_run if dry_run is not None else (not token)
    if force_dry and dry_run is None and not token:
        note = "no installation token: dry_run only (set GITHUB_APP_INSTALLATION_TOKEN or App JWT env)"
    else:
        note = None

    pr_url = f"https://github.com/{repo}/pull/{int(pr)}"
    argv = check_argv(pr_url, env)
    if plan.get("claim"):
        # claim text is advisory for logs; daily_run reads claims from PR body
        pass

    run_exit = None
    if force_dry:
        # still allow a pre-supplied record via plan["record"]
        rec = plan.get("record")
    else:
        from poc import tavily_docs
        missing = tavily_docs.missing_key_line(env)
        if missing:
            print(missing, file=sys.stderr)
            return {"ok": False, "error": missing, "action": action, "repo": repo, "pr": pr, "dry_run": False}
        if runner is not None:
            run_exit = runner(argv)
        else:
            from ops import daily_run
            run_exit = daily_run.main(argv)
        rec = plan.get("record") or _load_latest_record(str(repo), int(pr), env)

    if not isinstance(rec, dict):
        out = {"ok": run_exit == 0 if run_exit is not None else force_dry, "action": action,
               "repo": repo, "pr": pr, "dry_run": force_dry, "run_exit": run_exit,
               "note": note or "no record.json found after run"}
        return out

    report_path = write_hosted_report(rec, hosted_dir or hosted_reports_dir(env))
    url = report_url_for(report_path, env)
    verdict = str(rec.get("verdict") or "could_not_verify")
    reason = str(rec.get("reason") or "")
    head = plan.get("head_sha") or (rec.get("pr") or {}).get("head_sha") or ""
    gh_meta: dict[str, Any] = {"report_path": str(report_path), "report_url": url, "dry_run": force_dry}

    if force_dry or not token:
        gh_meta["note"] = note or "dry_run: check run and comment not posted"
        rec["github_app"] = gh_meta
        rec["posted_upstream"] = False
        return {"ok": True, "action": action, "repo": repo, "pr": pr, "dry_run": True,
                "verdict": verdict, "github_app": gh_meta, "run_exit": run_exit}

    try:
        payload = check_run_payload(str(repo), str(head), verdict, reason, url, env=env)
        check = post_check_run(str(repo), payload, token, env=env)
        comment = post_pr_comment(str(repo), int(pr), summary_comment(verdict, reason, url), token, env=env)
    except (GitHubAppError, PermissionError) as e:
        gh_meta["error"] = str(e)
        return {"ok": False, "action": action, "repo": repo, "pr": pr, "github_app": gh_meta,
                "run_exit": run_exit}

    gh_meta["check_run_id"] = check.get("id")
    gh_meta["check_run_url"] = check.get("html_url")
    gh_meta["comment_id"] = comment.get("id")
    gh_meta["comment_url"] = comment.get("html_url")
    rec["github_app"] = gh_meta
    rec["posted_upstream"] = True
    return {"ok": True, "action": action, "repo": repo, "pr": pr, "dry_run": False,
            "verdict": verdict, "github_app": gh_meta, "run_exit": run_exit}


def _esc(s) -> str:
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def state_dir(env: dict | None = None) -> Path:
    """Where the App keeps what must survive a restart: under POC_OPS_DIR (the deploy's data folder) when set."""
    env = os.environ if env is None else env
    base = (env.get("POC_OPS_DIR") or "").strip()
    return (Path(base) if base else REPO_ROOT / "ops") / "github-app"


def claim_delivery(delivery_id: str, root: Path) -> bool:
    """Record one X-GitHub-Delivery ID. True the first time, False for a duplicate (a redelivery or retry).

    The list is a file under the state dir, read and appended under an exclusive fcntl lock, so it holds
    across restarts and across processes."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / "deliveries.txt"
    with open(path, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.seek(0)
            if delivery_id in {ln.strip() for ln in fh}:
                return False
            fh.seek(0, os.SEEK_END)
            fh.write(delivery_id + "\n")
            fh.flush()
            os.fsync(fh.fileno())
            return True
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def daily_cap_refusal(env: dict) -> str | None:
    """App checks count toward POC_DAILY_CAP through the console's own counter (same file, same fcntl lock).

    Only on a hosted deploy (POC_HOSTED=1), where the console also counts; that call also requires
    POC_TAVILY_CREDIT_CAP. A local run is not capped."""
    from poc import console_api
    if not console_api.hosted_console(env):
        return None
    return console_api.hosted_budget_refusal(env)


class CheckQueue:
    """One worker thread runs queued checks one at a time, in arrival order."""

    def __init__(self, env: dict, apply_fn: Callable = None, refusal_fn: Callable = None):
        self.env = env
        self.apply_fn = apply_fn or apply
        self.refusal_fn = refusal_fn or daily_cap_refusal
        self.q: queue.Queue = queue.Queue()
        self.results: list[dict] = []
        self._worker: threading.Thread | None = None

    def start(self) -> CheckQueue:
        if self._worker is None:
            self._worker = threading.Thread(target=self._run, name="poc-app-worker", daemon=True)
            self._worker.start()
        return self

    def put(self, plan: dict) -> int:
        self.q.put(plan)
        return self.q.qsize()

    def run_one(self, plan: dict) -> dict:
        stop = self.refusal_fn(self.env)
        if stop:
            result = {"ok": False, "action": "refuse", "why": stop, "repo": plan.get("repo"), "pr": plan.get("pr")}
        else:
            try:
                result = self.apply_fn(plan, env=self.env)
            except Exception as e:  # noqa: BLE001 - one bad check must not stop the worker
                result = {"ok": False, "error": f"{type(e).__name__}: {e}", "repo": plan.get("repo"),
                          "pr": plan.get("pr")}
        self.results.append(result)
        print(f"app check {plan.get('repo')}#{plan.get('pr')}: ok={result.get('ok')} "
              f"{result.get('why') or result.get('error') or result.get('verdict') or ''}", flush=True)
        return result

    def _run(self) -> None:
        while True:
            plan = self.q.get()
            if plan is None:
                return
            try:
                self.run_one(plan)
            finally:
                self.q.task_done()

    def stop(self) -> None:
        if self._worker is not None:
            self.q.put(None)
            self._worker.join(timeout=10)
            self._worker = None


class _WebhookHandler(BaseHTTPRequestHandler):
    env: dict = os.environ  # overridden in serve()
    checks: CheckQueue | None = None
    state: Path = DEFAULT_HOSTED

    def log_message(self, fmt, *args):  # quieter
        pass

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.split("?")[0] in ("/health", "/"):
            queued = self.checks.q.qsize() if self.checks else 0
            self._json(200, {"ok": True, "service": "proof-of-change-github-app", "queued": queued})
            return
        self.send_error(404)

    def do_POST(self):  # noqa: N802
        if self.path.split("?")[0] != "/webhook":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        secret = self.env.get(WEBHOOK_SECRET_ENV)
        sig = self.headers.get("X-Hub-Signature-256")
        if not verify_webhook(raw, sig, secret):
            self.send_error(401, "bad signature")
            return
        delivery = (self.headers.get("X-GitHub-Delivery") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9-]{1,100}", delivery):
            self.send_error(400, "missing X-GitHub-Delivery")
            return
        event = self.headers.get("X-GitHub-Event") or ""
        try:
            payload = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            self.send_error(400, "bad json")
            return
        if not claim_delivery(delivery, self.state):
            self._json(200, {"duplicate": True, "delivery": delivery})
            return
        plan = handle_event(event, payload, self.env)
        if plan.get("action") in ("prove", "run") and self.checks is not None:
            position = self.checks.put(plan)
            self._json(202, {"queued": True, "delivery": delivery, "position": position,
                             "action": plan.get("action"), "repo": plan.get("repo"), "pr": plan.get("pr")})
            return
        self._json(200, {"delivery": delivery, "plan": plan})


def make_server(host: str, port: int, env: dict | None = None, *, checks: CheckQueue | None = None,
                state: Path | None = None) -> HTTPServer:
    env = os.environ if env is None else env

    class H(_WebhookHandler):
        pass

    H.env = env
    H.checks = checks if checks is not None else CheckQueue(env).start()
    H.state = state or state_dir(env)
    return HTTPServer((host, port), H)


def serve(host: str = "0.0.0.0", port: int = 8080, env: dict | None = None) -> None:
    httpd = make_server(host, port, env)
    print(f"proof-of-change github app listening on http://{host}:{port}  POST /webhook  GET /health "
          "(one check at a time; webhooks answered 202 when queued)", flush=True)
    httpd.serve_forever()


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Proof-of-Change GitHub App webhook server")
    ap.add_argument("--host", default=os.environ.get("POC_WEBHOOK_HOST", "0.0.0.0"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("POC_WEBHOOK_PORT", "8080")))
    a = ap.parse_args(argv)
    from poc import pdf_maker
    stop = pdf_maker.missing_refusal()  # every check here is a product check: no PDF maker, no start
    if stop:
        print(stop, file=sys.stderr, flush=True)
        return 1
    serve(a.host, a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
