"""Contree MCP tools for Proof-of-Change (stretch: prove_change, run_probe).

Expose as stdio JSON-RPC style tools when Contree MCP is wired; until then this module
is the contract and a local callable surface for tests.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from poc import probes as probe_mod

TOOLS = (
    {"name": "prove_change",
     "description": "Run Proof-of-Change on a PR (repo + pr number). Returns verdict + report path.",
     "inputSchema": {"type": "object", "required": ["repo", "pr"],
                     "properties": {"repo": {"type": "string"}, "pr": {"type": "integer"},
                                    "claim": {"type": "string"}}}},
    {"name": "run_probe",
     "description": "Run one probe script on both main and PR sides (paths to python + probe file).",
     "inputSchema": {"type": "object", "required": ["probe_path", "main_python", "pr_python"],
                     "properties": {"probe_path": {"type": "string"},
                                    "main_python": {"type": "string"},
                                    "pr_python": {"type": "string"},
                                    "timeout_s": {"type": "integer"}}}},
)


def list_tools() -> list[dict]:
    return list(TOOLS)


def prove_change(repo: str, pr: int, claim: str | None = None, *, dry_run: bool = True) -> dict[str, Any]:
    from poc.serverless import orchestrate
    return orchestrate({"repo": repo, "pr": pr, "claim": claim, "dry_run": dry_run, "allow_any_repo": dry_run})


def run_probe(probe_path: str, main_python: str, pr_python: str, timeout_s: int = 60) -> dict[str, Any]:
    """Execute one probe on both sides via subprocess; compare printed JSON observations."""
    path = Path(probe_path)
    if not path.is_file():
        return {"ok": False, "error": f"missing probe {probe_path}"}
    outs = {}
    for side, py in (("main", main_python), ("pr", pr_python)):
        try:
            r = subprocess.run([py, str(path)], capture_output=True, text=True, timeout=timeout_s, check=False)
            outs[side] = {"exit": r.returncode, "stdout": r.stdout[-4000:], "stderr": r.stderr[-1000:]}
        except Exception as e:  # noqa: BLE001
            outs[side] = {"exit": -1, "error": f"{type(e).__name__}: {e}"}
    main_obs = probe_mod.observations_of(outs.get("main", {}).get("stdout") or "",
                                         outs.get("main", {}).get("exit"))
    pr_obs = probe_mod.observations_of(outs.get("pr", {}).get("stdout") or "",
                                       outs.get("pr", {}).get("exit"))
    cmp = {"same": main_obs == pr_obs, "main": main_obs, "pr": pr_obs}
    return {"ok": True, "sides": outs, "comparison": cmp}


def dispatch(name: str, arguments: dict) -> dict:
    if name == "prove_change":
        return prove_change(arguments["repo"], int(arguments["pr"]), arguments.get("claim"),
                            dry_run=bool(arguments.get("dry_run", True)))
    if name == "run_probe":
        return run_probe(arguments["probe_path"], arguments["main_python"], arguments["pr_python"],
                         int(arguments.get("timeout_s") or 60))
    return {"ok": False, "error": f"unknown tool {name}"}


def main() -> None:
    """One-shot stdio: read one JSON {\"tool\",\"arguments\"}, print JSON result."""
    import sys
    req = json.loads(sys.stdin.read() or "{}")
    print(json.dumps(dispatch(req.get("tool") or "", req.get("arguments") or {})))


if __name__ == "__main__":
    main()
