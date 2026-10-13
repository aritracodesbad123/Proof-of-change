"""PatchGuru comparison runner: the published PatchGuru pipeline, run on benchmark cases with a Nemotron model on
Nebius instead of GPT-5-mini, inside our sandbox instead of Docker, writing our record format.

    python -m evals.patchguru_runner --bench bench/benchmark-v0.csv --ids B14 \
        --patchguru <PatchGuru checkout at PINNED_COMMIT> --fingerprints <fingerprints.json> --out runs/patchguru

What stays PatchGuru's own: its prompts and the order of its steps (intent analysis -> run the generated
specification -> repair loop on non-assertion errors -> self-review of assertion failures, re-run on MISMATCH),
taken by importing PatchGuru's own modules from a checkout pinned to PINNED_COMMIT.

What changes, and why:
* Model: every PatchGuru model call goes through `gated_query`, which (1) passes the exact prompt through the
  answer-key firewall (poc.model_gate.GatedProvider, so it cannot be skipped), (2) calls Nebius, and (3) saves the
  raw server response, including the server-reported model name, to raw/<n>.json. The run is labelled blind only
  if every call passed the firewall and every response was saved; otherwise it is a pilot.
* Execution: PatchGuru runs its generated specification in a Docker container of the pre-PR checkout. Here it runs
  in a bubblewrap sandbox (guardrails/sandbox.py, no network) over a venv of the pre-PR checkout.
* References: PatchGuru can also fetch issues and PRs mentioned in the PR comments. That is switched off: a later
  issue can describe the very regression we score, which would leak the answer.
* Scope: PatchGuru supports only PRs that change exactly one non-test function. `changed_functions` checks that
  first; other cases get the verdict could_not_verify with reason "not eligible".

Two records per case (the scorer reads them like any other baseline):
  <id>-patchguru_pre_review.json   verdict right after the repair loop: an assertion failure = needs_attention
  <id>-patchguru_post_review.json  verdict after the self-review step: BUG = needs_attention, NORMAL = verified
PatchGuru's own state, events and the raw model responses stay under logs/<id>/patchguru/.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
import time
import types
import urllib.request
from pathlib import Path

from poc.leakage import Fingerprints
from poc.model_gate import Gate, GatedProvider

PINNED_COMMIT = "c67d3fad51edf3bcfd9641a665f5115018a4d591"
BASE_URL = "https://api.tokenfactory.nebius.com/v1"
KEY_ENV = "NEBIUS_API_KEY"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"
BASELINES = ("patchguru-pre-review", "patchguru-post-review")


# ---------------------------------------------------------------- eligibility (PatchGuru: one non-test function)
def _is_test_path(path: str) -> bool:
    parts = path.lower().split("/")
    return any(p in ("tests", "test", "testing") for p in parts[:-1]) or parts[-1].startswith("test_") \
        or parts[-1].endswith("_test.py") or parts[-1] == "conftest.py"


def _functions(src: str) -> tuple[dict, str]:
    """{qualified name: source} for every function, and the module with all function bodies blanked (to spot
    changes outside functions)."""
    tree = ast.parse(src)
    out: dict[str, str] = {}

    def walk(node, prefix):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{ch.name}"
                out[name] = ast.unparse(ch)
                walk(ch, name + ".")
            elif isinstance(ch, ast.ClassDef):
                walk(ch, f"{prefix}{ch.name}.")

    walk(tree, "")

    class Blank(ast.NodeTransformer):
        def visit_FunctionDef(self, n):
            n.body, n.decorator_list, n.returns = [ast.Pass()], [], None
            n.args = ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[])
            return n
        visit_AsyncFunctionDef = visit_FunctionDef

    def strip_docs(t):
        for n in ast.walk(t):
            if isinstance(n, (ast.Module, ast.ClassDef)) and n.body and isinstance(n.body[0], ast.Expr) \
                    and isinstance(getattr(n.body[0], "value", None), ast.Constant) \
                    and isinstance(n.body[0].value.value, str):
                n.body = n.body[1:] or [ast.Pass()]
        return t

    return out, ast.dump(strip_docs(Blank().visit(tree)))


def changed_functions(before: dict[str, str | None], after: dict[str, str | None]) -> dict:
    """before/after: {path: source or None (file absent)} for the PR's changed files. Returns
    {"eligible": bool, "functions": [(path, qualified name)], "why": str}."""
    changed, problems = [], []
    for path in sorted(set(before) | set(after)):
        if not path.endswith(".py") or _is_test_path(path):
            continue
        b, a = before.get(path), after.get(path)
        if b is None or a is None:
            problems.append(f"{path} is {'added' if b is None else 'removed'}")
            continue
        try:
            fb, mb = _functions(b)
            fa, ma = _functions(a)
        except SyntaxError as e:
            problems.append(f"{path} does not parse: {e.msg}")
            continue
        if mb != ma:
            problems.append(f"{path} changes code outside functions (imports, classes or module-level code)")
        for name in sorted(set(fb) | set(fa)):
            if fb.get(name) != fa.get(name):
                if any(name.startswith(o + ".") for _p, o in changed):
                    continue   # a nested function inside an already-counted one
                kind = "added" if name not in fb else "removed" if name not in fa else "changed"
                changed.append((path, name))
                if kind != "changed":
                    problems.append(f"{path}:{name} is {kind}")
    if not changed and not problems:
        problems.append("no non-test Python function changes")
    if len(changed) > 1:
        problems.append(f"{len(changed)} functions change: " + ", ".join(n for _p, n in changed))
    ok = not problems and len(changed) == 1
    return {"eligible": ok, "functions": changed,
            "why": "exactly one non-test function changes" if ok else "; ".join(problems)}


# ---------------------------------------------------------------- model access: firewall + raw responses
class NebiusChat(GatedProvider):
    """Plain-text chat completions (PatchGuru parses free text). complete_json (inherited) checks the prompt
    through the gate first; _call sends it and saves the raw server response."""

    name = "nebius-patchguru"

    def __init__(self, gate: Gate, model: str, raw_dir: Path, key: str, base_url: str = BASE_URL,
                 timeout: int = 600, transport=None):
        super().__init__(gate=gate, models={"chat": model})
        self._key, self.base_url, self.timeout = key, base_url.rstrip("/"), timeout
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.calls: list[dict] = []
        self._transport = transport or self._http

    def _http(self, body: dict) -> dict:
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self._key}"},
                                     method="POST")  # br-allow-external: model inference call, creates nothing
        with urllib.request.urlopen(req, timeout=self.timeout) as r:   # noqa: S310 (fixed https URL)
            return json.loads(r.read())

    def _call(self, task: str, system: str, user: str, schema: dict, ctx: dict) -> dict:
        body = {"model": self.models["chat"], "temperature": ctx.get("temperature", 0.7),
                "max_tokens": ctx.get("max_tokens", 16384), "messages": [{"role": "user", "content": user}]}
        n = len(self.calls) + 1
        t0 = time.time()
        data = self._transport(body)
        path = self.raw_dir / f"{n:03d}-{task}.json"
        path.write_text(json.dumps({"request": {k: v for k, v in body.items() if k != "messages"},
                                    "prompt": user, "response": data}, indent=1))
        served = data.get("model")
        self.calls.append({"n": n, "task": task, "requested_model": body["model"], "server_model": served,
                           "raw": path.name, "seconds": round(time.time() - t0, 1),
                           "usage": data.get("usage")})
        return {"text": data["choices"][0]["message"]["content"] or ""}

    def summary(self) -> dict:
        gate_log = self.gate.log if self.gate else []
        all_gated = bool(gate_log) and all(g.get("ok") for g in gate_log) and len(gate_log) == len(self.calls)
        all_raw = bool(self.calls) and all(c["server_model"] and (self.raw_dir / c["raw"]).exists()
                                           for c in self.calls)
        return {"calls": len(self.calls), "firewall_checked": len(gate_log), "firewall_all_passed": all_gated,
                "raw_saved_with_server_model": all_raw, "server_models": sorted({str(c["server_model"])
                                                                                 for c in self.calls}),
                "blind": all_gated and all_raw, "call_log": self.calls}


_CURRENT: dict = {}


def install_query_llm(chat: NebiusChat) -> None:
    """Replace PatchGuru's OpenAI module with one whose query_llm goes through `chat`. Must run before any other
    PatchGuru module is imported (they import query_llm by name)."""
    _CURRENT["chat"] = chat
    if "patchguru.llms.OpenAI" in sys.modules and getattr(sys.modules["patchguru.llms.OpenAI"], "_poc", False):
        return   # already installed; PatchGuru modules hold query_llm by name, so it reads _CURRENT on each call
    mod = types.ModuleType("patchguru.llms.OpenAI")
    mod._poc = True

    def query_llm(prompt, model=None, temperature=0.7, max_tokens=16384):
        return _CURRENT["chat"].complete_json("patchguru", "", prompt, {}, {"temperature": temperature,
                                                               "max_tokens": max_tokens})["text"]

    mod.query_llm = query_llm
    sys.modules["patchguru.llms.OpenAI"] = mod
    # Parts of PatchGuru this runner replaces (GitHub fetching, Docker): stubs, so their heavy dependencies (Docker
    # SDK, language server, PyGithub) are not needed. Calling any of them is a bug and fails loudly.
    def unused(*_a, **_k):
        raise RuntimeError("replaced by the Proof-of-Change runner")
    for name, attrs in {"patchguru.analysis.PRRetriever": ("retrieve_pr", "get_repo"),
                        "patchguru.execution.DockerExecutor": ("DockerExecutor",),
                        "github": ("Github", "Auth")}.items():
        stub = types.ModuleType(name)
        for at in attrs:
            setattr(stub, at, unused)
        stub.GithubException = type("GithubException", (Exception,), {})
        sys.modules[name] = stub


# ---------------------------------------------------------------- verdicts from PatchGuru's states
def verdicts(states: dict) -> dict:
    """PatchGuru final states -> our verdicts before and after its self-review step."""
    execs = states.get("execution_status") or []
    traces = states.get("review_traces") or []
    if not states.get("intent_analysis"):
        why = "PatchGuru could not produce a specification"
        return {"pre": ("could_not_verify", why), "post": ("could_not_verify", why)}
    # PatchGuru repairs assertion failures in the pre-PR version itself and only sends a failure on the PR's
    # version to self-review, so "reached self-review" is exactly "flagged before self-review".
    if traces or states.get("review_conclusion") == "BUG":
        pre = ("needs_attention", "the generated specification failed an assertion on the PR's version of the "
                                  "function (before self-review)")
    elif execs and execs[-1].get("exit_code") == 0:
        pre = ("verified", "the generated specification ran and passed")
    else:
        pre = ("could_not_verify", "the generated specification never ran cleanly after the repair attempts")
    concl = states.get("review_conclusion")
    if states.get("stage") == "completed" and concl == "BUG":
        post = ("needs_attention", "self-review kept the failing assertion as a real bug")
    elif states.get("stage") == "completed" and concl == "NORMAL":
        post = ("verified", "no assertion failures remained" + (" after self-review revised the specification"
                                                                if traces else ""))
    else:
        post = ("could_not_verify", f"PatchGuru stopped at stage {states.get('stage')!r}")
    return {"pre": pre, "post": post}


# ---------------------------------------------------------------- one case
def _file_at(src: Path, sha: str, path: str) -> str | None:
    import subprocess
    r = subprocess.run(["git", "-C", str(src), "show", f"{sha}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def _pr_details(text: dict, row: dict) -> str:
    """PatchGuru's pull-request block, from what our bench mode already permits: title, description (as at merge
    when the edit history can be read) and nothing fetched from later issues."""
    return (f"### Title\n#{row['pr']}: {text['title']}\n\n### Comments\nComment by author:\n{text['body']}\n\n"
            "### Review comments\n\n### Commit messages\n")


def _sandbox_executor(dr, venv: Path, timeout: int):
    """PatchGuru's DockerExecutor.execute_python_code, as a no-network sandbox run in the pre-PR venv."""
    counter = {"n": 0}

    def execute_python_code(code: str, timeout_s: int = timeout):
        counter["n"] += 1
        cwd = dr.side_cwd(venv)
        f = cwd / f"spec_{counter['n']:02d}.py"
        f.write_text(code)
        r = dr.in_side(venv, [venv / "bin/python", f.name], cwd=cwd, timeout=timeout_s)
        out = (r.stdout or "") + (r.stderr or "")
        rc = 124 if r.returncode == "timeout" else r.returncode
        return rc, out
    return execute_python_code


def run_case(row: dict, a, fp: Fingerprints, key: str, out: Path, machine: dict) -> list[dict]:
    from ops import bench
    from ops import daily_run as dr
    rid = row["id"]
    t0 = time.time()
    logd = out / "logs" / rid
    pgd = logd / "patchguru"
    pgd.mkdir(parents=True, exist_ok=True)
    work = Path(a.work_dir).resolve() / "patchguru" / rid
    import shutil
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    base = {"case_id": rid, "bench": {"id": rid, "answer_key_read": False,
                                      "main_sha_merge_first_parent": row["main_sha_merge_first_parent"],
                                      "pr_side_sha_merge_commit": row["pr_side_sha_merge_commit"]},
            "repo": row["repo"], "pr": {"number": int(row["pr"]), "url": row["pr_url"], "title": row["pr_title"]},
            "tool": {"name": "PatchGuru", "commit": PINNED_COMMIT, "model": a.model, "provider": "nebius",
                     "executor": "bubblewrap sandbox, no network (replaces Docker)", "references": "off"},
            "poc_commit": _git_head(), "machine": machine, "label": "not run"}

    def records(pre, post, extra) -> list[dict]:
        recs = []
        for bl, (v, why) in zip(BASELINES, (pre, post)):
            r = dict(base, **extra, baseline=bl, verdict=v, reason=why,
                     id=f"bench-{rid}-{row['repo'].replace('/', '-')}-{row['pr']}-{bl}",
                     elapsed_s=round(time.time() - t0, 1))
            (out / f"{rid}-{bl.replace('-', '_')}.json").write_text(json.dumps(r, indent=1))
            recs.append(r)
        return recs

    co = bench.checkout(dr, row, work, logd / "git.log")
    if not co.get("ok"):
        why = co.get("why", "checkout failed")
        return records(("could_not_verify", why), ("could_not_verify", why), {"label": "pilot"})
    src = work / "src"
    files = co["files"]
    before = {f: _file_at(src, co["main_sha"], f) for f in files}
    after = {f: _file_at(src, co["pr_sha"], f) for f in files}
    elig = changed_functions(before, after)
    (logd / "eligibility.json").write_text(json.dumps(elig, indent=1))
    if not elig["eligible"]:
        why = "not eligible for PatchGuru: " + elig["why"]
        return records(("could_not_verify", why), ("could_not_verify", why),
                       {"eligibility": elig, "label": "not run"})

    # PatchGuru inputs, built the way its PullRequest/SpecInfer code builds them
    path, qname = elig["functions"][0]
    fname = qname.split(".")[-1]
    pre_src = _function_source(before[path], qname)
    post_src = _function_source(after[path], qname)
    module = path.removeprefix("src/").removesuffix(".py").replace("/", ".").removesuffix(".__init__")
    text = bench.pr_text(dr, row)

    # model access (firewall + raw saving) and PatchGuru import
    gate = Gate(fp, pr=f"{row['repo']}#{row['pr']}")
    chat = NebiusChat(gate, a.model, pgd / "raw", key)
    sys.path.insert(0, str(Path(a.patchguru).resolve()))
    from patchguru import Config
    Config.LLM_MODEL, Config.USE_REFERENCE, Config.USE_REFERENCE_SUMMARY = a.model, False, False
    Config.LOG_DIR = str(pgd / "events")
    install_query_llm(chat)
    from patchguru import SpecInfer
    from patchguru.utils.PythonCodeUtil import (
        convert_import_dict_to_string,
        extract_imported_modules,
        get_function_signature,
        update_function_name,
    )

    prev_code = f"### {qname}\n{update_function_name(pre_src, fname, 'pre_' + fname)}\n\n"
    post_code = f"### {qname}\n{update_function_name(post_src, fname, 'post_' + fname)}\n\n"
    post_sig = f"## {qname}\n{get_function_signature(update_function_name(post_src, fname, 'post_' + fname))}\n\n"
    try:
        imports = convert_import_dict_to_string(extract_imported_modules(before[path]))
    except Exception:  # noqa: BLE001
        imports = ""
    # A `from __future__` line must be the first statement of a file; PatchGuru pastes these imports mid-file, so
    # they are dropped (they change nothing at run time on Python 3.11+ for this use).
    imports = f"from {module} import *\n" + "".join(ln + "\n" for ln in imports.splitlines()
                                                    if not ln.startswith("from __future__"))
    enclosing = ""
    if "." in qname:
        enclosing = f"class {qname.split('.')[-2]}:  # enclosing class of the function under test\n"

    # pre-PR environment (PatchGuru's 'pre_commit container')
    venv = work / "venv-main"
    wheels = dict(x.split("=", 1) for x in (a.wheel or []))
    if rid in wheels:   # no compiler for a source build: approximate the pre-PR env with a released wheel
        base["environment"] = f"released wheel {wheels[rid]} (approximation of the pre-PR commit)"
        env = dr.base_env(dr.side_home(venv), install=True)
        sbx = dr.side_sandbox(venv, network=True)
        ok, why = True, ""
        for c in (["uv", "venv", "-q", "-p", a.python_full, venv],
                  ["uv", "pip", "install", "-q", "-p", venv / "bin/python", wheels[rid]]):
            rc, _ = dr.run(c, logd / "setup-main.log", env=env, timeout=a.build_timeout, sbx=sbx)
            if rc != 0:
                ok, why = False, f"wheel install failed ({rc})"
                break
    else:
        ok, why = dr.install_side(venv, work / "side-main", None, logd / "setup-main.log", a.python_full,
                                  a.build_timeout, None)
    if not ok:
        return records(("could_not_verify", why), ("could_not_verify", why), {"eligibility": elig})

    class Executor:
        def __init__(self, container_name=None):
            self.execute_python_code = _sandbox_executor(dr, venv, a.spec_timeout)

    class Repo:
        container_name = "sandbox"

    class Manager:
        def get_cloned_repo(self, _commit):
            return Repo()

    class PR:
        pre_commit, import_string = co["main_sha"], imports

    SpecInfer.DockerExecutor = Executor
    states = SpecInfer.spec_infer(
        pr_nb=int(row["pr"]), force=True, cache_dir=str(pgd), pull_request_details=_pr_details(text, row),
        prev_fut_code=prev_code, post_fut_code=post_code, prev_fut_names=qname, post_fut_signatures=post_sig,
        enclosing_class=enclosing, pr=PR(), cloned_repo_manager=Manager(), fut_name=fname,
        code_changes=co["diff"], summary_queries=0)
    (pgd / "final_states.json").write_text(json.dumps(states, indent=1, default=str))
    v = verdicts(states)
    s = chat.summary()
    label = "blind" if s["blind"] else "pilot"
    return records(v["pre"], v["post"], {"eligibility": elig, "label": label, "model_calls": s,
                                         "patchguru_raw": str((pgd).relative_to(out))})


def _function_source(src: str, qname: str) -> str:
    import textwrap
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    parts = qname.split(".")
    node = tree
    for p in parts:
        node = next(n for n in ast.iter_child_nodes(node)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == p)
    start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
    return textwrap.dedent("".join(lines[start:node.end_lineno]))


def _git_head() -> str | None:
    import subprocess
    r = subprocess.run(["git", "-C", str(Path(__file__).resolve().parent.parent), "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    return r.stdout.strip() or None


def main(argv=None) -> int:
    from ops import bench
    from ops import daily_run as dr
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--bench", required=True, help="benchmark INPUTS csv (never an answer key)")
    ap.add_argument("--ids", default=None)
    ap.add_argument("--patchguru", required=True, help=f"PatchGuru checkout at {PINNED_COMMIT[:12]}")
    ap.add_argument("--fingerprints", required=True,
                    help="answer-key fingerprints JSON (python -m poc.leakage fingerprint); hashes only")
    ap.add_argument("--out", default="runs/patchguru")
    ap.add_argument("--work-dir", default="ops/work")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--python", default="3.12")
    ap.add_argument("--build-timeout", type=int, default=1800)
    ap.add_argument("--spec-timeout", type=int, default=300)
    ap.add_argument("--wheel", action="append", metavar="ID=REQ",
                    help="use a released wheel for the pre-PR environment, e.g. B02=pandas==2.1.4")
    ap.add_argument("--eligibility-only", action="store_true", help="report which cases qualify; no model calls")
    a = ap.parse_args(argv)
    rows = bench.select(bench.read_inputs(a.bench), a.ids)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.eligibility_only:
        return _eligibility(rows, a, out)
    fp = Fingerprints.from_json(json.loads(Path(a.fingerprints).read_text()))
    key = os.environ.pop(KEY_ENV, "")   # held here only; PatchGuru's code and the sandbox never see it in env
    if not key:
        print(f"Stopped: {KEY_ENV} is not set", file=sys.stderr)
        return 2
    a.python_full = dr.resolve_python(a.python)
    machine = dict(dr.detect_machine_type())
    for row in rows:
        print(f"[{row['id']}] {row['repo']}#{row['pr']} ...", flush=True)
        for r in run_case(row, a, fp, key, out, machine):
            print(f"    {r['baseline']}: {r['verdict']} ({r.get('label')}): {r['reason'][:140]}", flush=True)
    return 0


def _eligibility(rows: list[dict], a, out: Path) -> int:
    from ops import bench
    from ops import daily_run as dr
    res = {}
    for row in rows:
        work = Path(a.work_dir).resolve() / "patchguru-elig" / row["id"]
        import shutil
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        co = bench.checkout(dr, row, work, work / "git.log")
        if not co.get("ok"):
            res[row["id"]] = {"eligible": False, "why": co.get("why")}
        else:
            src = work / "src"
            res[row["id"]] = changed_functions({f: _file_at(src, co["main_sha"], f) for f in co["files"]},
                                               {f: _file_at(src, co["pr_sha"], f) for f in co["files"]})
        print(f"{row['id']}: {'ELIGIBLE' if res[row['id']]['eligible'] else 'no'} - {res[row['id']]['why']}",
              flush=True)
    (out / "eligibility.json").write_text(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
