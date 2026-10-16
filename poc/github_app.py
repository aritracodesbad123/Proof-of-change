"""GitHub App surface for Proof-of-Change (REQUIREMENTS §4 steps 0/10).

Posts only to allowlisted demo/mirror repos (G-ext). Never blocks merges: check runs are
neutral/success advice only. Local HTML reports stay the offline path.

Wire a real App: set GITHUB_APP_ID / GITHUB_APP_PRIVATE_KEY / GITHUB_WEBHOOK_SECRET and
POC_DEMO_REPOS=owner/repo,... then point the App webhook at POST /webhook.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from pathlib import Path

DEMO_REPOS_ENV = "POC_DEMO_REPOS"
PROVE_RE = re.compile(r"^/prove(?:\s+(.+))?$", re.I | re.M)


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


def check_run_payload(repo: str, head_sha: str, verdict: str, summary: str, report_url: str | None = None) -> dict:
    """GitHub check-run body. Conclusion is always success/neutral — never failure (non-blocking)."""
    if not may_post(repo):
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
    """Minimal dispatcher: returns an action plan; does not call GitHub until credentials exist."""
    env = os.environ if env is None else env
    repo = ((payload.get("repository") or {}).get("full_name") or "")
    if event == "issue_comment" and payload.get("action") == "created":
        body = ((payload.get("comment") or {}).get("body") or "")
        claim = parse_prove(body)
        if claim is None:
            return {"action": "ignore", "why": "not a /prove comment"}
        if not may_post(repo, env):
            return {"action": "refuse", "why": f"repo {repo} not in {DEMO_REPOS_ENV}"}
        return {"action": "prove", "repo": repo, "claim": claim,
                "pr": (payload.get("issue") or {}).get("number")}
    if event in ("pull_request", "check_suite"):
        if not may_post(repo, env):
            return {"action": "refuse", "why": f"repo {repo} not in {DEMO_REPOS_ENV}"}
        return {"action": "run", "repo": repo, "event": event}
    return {"action": "ignore", "why": f"unhandled event {event}"}


def write_hosted_report(rec: dict, out_dir: Path) -> Path:
    """Static behavior-map HTML for one PR record (hosted or opened locally)."""
    out_dir = Path(out_dir)
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
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Proof-of-Change { _esc(rid) }</title>
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
<p>Claims → probes (coloured by label). Model labels are advisory; code owns the verdict.</p>
<h3>Claims</h3>
<table><tr><th>Id</th><th>Claim</th><th>Status</th></tr>{rows_c or '<tr><td colspan=3>none</td></tr>'}</table>
<h3>Probes</h3>
<table><tr><th>Id</th><th>About</th><th>Labels</th></tr>{rows_p or '<tr><td colspan=3>none</td></tr>'}</table>
<h2>Summary</h2>
<p>{_esc(expl) or '(no model summary)'}</p>
<p class="meta">Agents: {_esc(json.dumps(agents.get('roles') or agents.get('status') or 'none'))}</p>
</body></html>"""
    path.write_text(html)
    return path


def _esc(s) -> str:
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
