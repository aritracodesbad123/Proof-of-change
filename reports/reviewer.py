"""Reviewer report: one report per observation record, for a human approver.

Ported from Jonathan's reference generator (feat/reviewer-report @ 3734001, harness/report/render_report.py,
spec docs/REPORT_SPEC.md) and folded into this package so there is one report generator. Entry point:
`python -m reports.generate` (see reports/generate.py). Changes from the reference are listed in
docs/REPORT_SPEC.md, section "Adopted by Nathan":

* Nathan's evals and guardrails (evals.checks.evaluate_record) are a section of every report. Any eval FAIL makes
  the verdict COULD NOT VERIFY / Re-run, because the run itself is not trustworthy.
* Golden cases come from evals/golden_cases.json, checked against the stored golden records
  (evals/fixtures/golden_v1.jsonl by default) with the same code as the eval gate.
* Every claim row (and every "unmentioned change" row) cites a log line: file, line number and quoted text.
  The report re-verifies its own citations with evals.checks.check_citations.
* Optional schema rev 2 fields are read when present: pr, claims, upstream_commit_old/new, per_test_outcomes,
  old_output, golden_check, reviewer_decision.
* The rerun command uses this repo's wrapper (`python -m harness.run`), which enforces 3 runs per side.

Rule: every number comes from the record or the run artifacts. Anything missing is printed as "not available".
Standard library only; PDF via headless Chrome or Chromium.
"""
from __future__ import annotations

import datetime
import glob
import html
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from evals.checks import Result, check_citations, check_golden_case, evaluate_record, golden_for, load_golden, recommendation
from guardrails.schema import SCHEMA_ID, schema_reference_note

GENERATOR_VERSION = "1.0 (from Jonathan's render_report.py 0.1)"
NA = "not available"
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
REPO = Path(__file__).resolve().parent.parent
GOLDEN_RECORDS = REPO / "evals" / "fixtures" / "golden_v1.jsonl"

# Fix advice per runner gate (copy of Jonathan's harness/brlib.py FIXES).
GATE_FIXES = {
    "env_identical_except_upstream": "freeze-diff.txt shows more than the upstream line. Usually the new upstream pulled in a "
                                     "dependency. Rerun; if it persists, add the dependency pin to --extra-pkgs so both sides get it.",
    "no_secrets_in_logs": "Credential-like strings were found and redacted. Find where they entered the environment and remove "
                          "them before the next run.",
    "old_side_healthy": "The OLD side did not run cleanly (no tests passed, or collection errors). Usually a missing test "
                        "dependency or the wrong test path. Read the collection errors in pytest-old-1.log, add the missing "
                        "packages with --extra-pkgs or fix --tests, then rerun. Results from this run are not trustworthy.",
    "runs_complete": "A side has fewer than the required runs or a run produced no JUnit XML. Look at the pytest-<side>-<n>.log "
                     "tail; if it timed out, raise --run-timeout or choose a smaller documented subset, then rerun.",
    "schema_valid": "The record does not match harness/schema/observation.schema.json. Fix the harness (this is a bug), then rerun.",
    "stability": "Outcomes changed between runs on the same side. List the tests in class-flaky.txt, rerun them alone with "
                 "-p no:randomly, and exclude confirmed flaky tests with --deselect (document it in subset_note).",
    "threads_pinned": "The thread variables were not 1 inside the test process. Do not override OMP/MKL/OPENBLAS_NUM_THREADS; rerun.",
    "venv_isolated": "A venv can see system site-packages. Recreate it with 'uv venv' (never --system-site-packages) and rerun.",
    "versions_verified": "The installed versions in freeze-old.txt / freeze-new.txt do not match the request. Check setup.log for "
                         "resolver messages; pin the dependent with --dep-version and rerun.",
}
GATE_LABELS = {
    "versions_verified": "Correct versions installed", "env_identical_except_upstream": "Only the upstream version differs between sides",
    "venv_isolated": "Isolated environments", "threads_pinned": "Thread count pinned to 1", "runs_complete": "All runs completed",
    "old_side_healthy": "Old side healthy (baseline is trustworthy)", "stability": "Repeatable results",
    "no_secrets_in_logs": "No secrets in logs", "schema_valid": "Record format valid",
}
GLOSSARY = [
    ("Old side / new side", "The same dependent library tested twice: once with the old version of the upstream library, once "
                            "with the new one. Nothing else differs."),
    ("Upstream", "The library being changed (for example pandas). The PR or release under review belongs to it."),
    ("Dependent", "A library that uses the upstream. Its own tests are our test subject."),
    ("Real break", "A test that passed in every old run and failed in every new run. This is a behavior change caused by the "
                   "upstream change."),
    ("Import failure", "A test module that cannot even be loaded on the new side, so none of its tests can run. Counted per module."),
    ("Lost tests", "Tests that passed before but could not run after, because their module failed to load. Not counted as real breaks."),
    ("Already broken", "Tests that failed before the change too. Not caused by the change."),
    ("Flaky", "Tests whose result changes between runs on the same side. They are not trusted either way."),
    ("Error signature", "The error message with numbers and file paths removed, so identical failures group together."),
    ("Gate", "An automatic check by the runner that the run itself is trustworthy (right versions, same environment, enough "
             "runs). Required gates must pass for the result to count."),
    ("Eval", "Nathan's independent check of the record (schema, versions, runs per side, threads, golden cases, citations). "
             "Any eval failure means the run cannot be trusted."),
    ("Golden case", "A known example with a known answer. If the tool still gets the golden cases right, its answers on new "
                    "cases are more believable."),
    ("Stability", "Share of tests that gave the same result in every run on one side. 1.0 means fully repeatable."),
    ("Citation", "A file name, line number and quoted text from a run log that backs a statement in the report."),
    ("JUnit XML", "The machine-readable test result file pytest writes for each run."),
    ("Freeze", "The exact list of installed packages and versions on each side."),
]
EMOJI = {"green": "🟢", "amber": "🟠", "red": "🔴", "grey": "⚪", "blue": "🔵"}
STATUS_COLOUR = {"proven": "green", "false": "red", "unmentioned change": "amber", "not testable": "grey"}
EVAL_COLOUR = {"pass": "green", "fail": "red", "warn": "amber", "skip": "grey", "todo": "grey"}
ACTION_COLOUR = {"Approve": "green", "Approve with notes": "green", "Reject": "red", "Re-run": "grey"}
ORDER = {("NEEDS ATTENTION", "Reject"): 0, ("NEEDS ATTENTION", "Approve with notes"): 1, ("COULD NOT VERIFY", "Re-run"): 2,
         ("VERIFIED", "Approve with notes"): 3, ("VERIFIED", "Approve"): 4}


# ---------------------------------------------------------------- helpers

def normalise(msg: str | None) -> str:
    """Same normalisation as harness/br_run.py signature(), so groups line up with the record."""
    msg = re.sub(r"^(E\s+)+", "", (msg or "").strip())
    s = re.sub(r"0x[0-9a-fA-F]+", "0x?", msg)
    s = re.sub(r"(/[\w.-]+)+/(site-packages|runs)/[^\s'\"]*", "<path>", s)
    s = re.sub(r"\b\d+(\.\d+)?\b", "N", s)
    return s[:160]


def tidy(sig: str | None) -> str:
    """Display form of a signature: drop a dangling '(<path>' left by path normalisation."""
    return re.sub(r"\s*\(<path>$", "", sig or "")


def first_line(msg: str | None) -> str:
    return next((ln.strip() for ln in (msg or "").splitlines() if ln.strip()), "")


def e_lines(text: str | None, n: int = 8) -> list[str]:
    """The 'E ' lines of a pytest traceback (the actual error output), last n of them, deduplicated."""
    found = [ln.strip()[1:].strip() for ln in (text or "").splitlines() if ln.strip().startswith("E ")]
    seen: set[str] = set()
    uniq = []
    for ln in found:
        if ln and ln not in seen:
            seen.add(ln)
            uniq.append(ln)
    return uniq[-n:]


def get(d, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d or d[p] is None:
            return default
        d = d[p]
    return d


def fmt(v) -> str:
    return NA if v is None or v == "" else str(v)


def read_lines(p: str) -> list[str] | None:
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return [ln.strip() for ln in fh if ln.strip()]


def parse_junit(path: str) -> dict | None:
    """test id -> (outcome, message, text). outcome in passed/failed/error/skipped."""
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return None
    out = {}
    for tc in root.iter("testcase"):
        tid = f"{tc.get('classname', '')}::{tc.get('name', '')}"
        oc, msg, txt = "passed", "", ""
        for ch in tc:
            if ch.tag in ("failure", "error"):
                oc, msg, txt = ("error" if ch.tag == "error" else "failed"), ch.get("message", ""), ch.text or ""
                break
            if ch.tag == "skipped":
                oc, msg = "skipped", ch.get("message", "")
        out[tid] = (oc, msg, txt)
    return out


def badge(colour: str, text: str) -> tuple:
    return ("badge", colour, text)


def link(text: str, href: str) -> str:
    return f"[{text}]({href})"


class Report:
    """Format-neutral list of blocks; the md and html renderers turn it into text."""

    def __init__(self):
        self.blocks: list[tuple] = []

    def h(self, level, text, anchor=None):
        self.blocks.append(("h", level, text, anchor))

    def p(self, text, cls=None):
        self.blocks.append(("p", text, cls))

    def table(self, headers, rows):
        self.blocks.append(("table", headers, rows))

    def bullets(self, items):
        self.blocks.append(("ul", items))

    def checklist(self, items):
        self.blocks.append(("check", items))

    def code(self, text):
        self.blocks.append(("code", text))

    def banner(self, verdict, action, confidence, reason, colour, scope):
        self.blocks.append(("banner", verdict, action, confidence, reason, colour, scope))


# ---------------------------------------------------------------- inputs

def resolve_run_dir(rec: dict, runs_root=None, record_path=None) -> str | None:
    """The run's artifact directory: <runs_root>/<logs>, <runs_root>/<basename(logs)>, or the record file's directory."""
    cands = []
    if runs_root and rec.get("logs"):
        cands += [Path(runs_root) / rec["logs"], Path(runs_root) / Path(rec["logs"]).name]
    if record_path:
        cands.append(Path(record_path).resolve().parent)
    for c in cands:
        if c.is_dir() and (any(c.glob("junit-*.xml")) or any(c.glob("pytest-*.log")) or (c / "args.json").exists()):
            return str(c)
    return None


def load_claims(rec: dict, claims_path=None) -> dict | None:
    if claims_path and os.path.exists(claims_path):
        with open(claims_path) as fh:
            return json.load(fh)
    return rec.get("claims") or None


def load_junit(rd: str | None) -> dict:
    junit = {}
    for f in sorted(glob.glob(os.path.join(rd, "junit-*-*.xml"))) if rd else []:
        m = re.match(r"junit-(old|new)-(\d+)\.xml", os.path.basename(f))
        if m:
            junit[(m.group(1), int(m.group(2)))] = parse_junit(f)
    return junit


def load_records_file(path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def golden_status(golden_records: list[dict], cases: list[dict] | None = None) -> list[dict]:
    """Every golden case re-checked against its stored record with the eval gate's own code (no re-run)."""
    cases = load_golden() if cases is None else cases
    out = []
    for c in cases:
        hits = [r for r in golden_records if golden_for(r, [c])]
        if not hits:
            out.append({"case": c["name"], "run": None, "harness": None, "ok": None, "detail": "no stored record for this case"})
            continue
        res = check_golden_case(hits[0], c)
        out.append({"case": c["name"], "run": hits[0].get("id"), "harness": hits[0].get("harness_version"),
                    "ok": res.status == "pass", "detail": res.detail})
    return out


def run_args(rd: str | None) -> dict | None:
    if rd and os.path.exists(os.path.join(rd, "args.json")):
        with open(os.path.join(rd, "args.json")) as fh:
            return json.load(fh)
    return None


# ---------------------------------------------------------------- analysis

def outcomes(junit: dict, tid: str, side: str) -> list[str]:
    return [(junit[(s, n)] or {}).get(tid, ("absent", "", ""))[0] for (s, n) in sorted(junit) if s == side]


def break_groups(rd: str | None, junit: dict):
    """Group real breaks by normalised error signature, from class-real_break.txt + new-side JUnit."""
    tests = read_lines(os.path.join(rd, "class-real_break.txt")) if rd else None
    if tests is None:
        return None
    groups: dict[str, dict] = {}
    first_new = min((n for (s, n) in junit if s == "new"), default=None)
    for t in tests:
        oc, msg, txt = (junit.get(("new", first_new)) or {}).get(t, ("absent", "", "")) if first_new else ("absent", "", "")
        sig = normalise(first_line(msg)) or "(no message in JUnit)"
        g = groups.setdefault(sig, {"tests": [], "example": None})
        g["tests"].append(t)
        if g["example"] is None:
            g["example"] = {"test": t, "message": msg, "text": txt, "old": outcomes(junit, t, "old"), "new": outcomes(junit, t, "new")}
    return sorted(groups.items(), key=lambda kv: -len(kv[1]["tests"]))


def import_group(rec: dict, rd: str | None, junit: dict):
    mods = read_lines(os.path.join(rd, "class-import_failure.txt")) if rd else None
    if not mods:
        return None
    bad = {k: v for k, v in (get(rec, "dependent_import", "new") or {}).items() if v != "ok"}
    sig = normalise(next(iter(bad.values()))) if bad else None
    if not sig:  # fall back to the first collection error in new JUnit
        for (s, _n), j in sorted(junit.items()):
            if s == "new" and j:
                for _t, (oc, msg, txt) in j.items():
                    if oc == "error":
                        sig = normalise(e_lines(txt, 1)[0] if e_lines(txt, 1) else first_line(msg))
                        break
            if sig:
                break
    return {"modules": mods, "signature": sig or NA, "package_errors": bad,
            "lost": read_lines(os.path.join(rd, "class-lost_tests.txt")) or []}


def consistency(rec: dict, groups, imp) -> list:
    """Cross-check: counts recomputed from the artifacts must equal the record's classification."""
    c = rec.get("classification") or {}
    if groups is None:
        return [badge("grey", NA), "run artifacts not available; counts are taken from the record only"]
    probs = []
    if sum(len(g["tests"]) for _, g in groups) != c.get("real_break", 0):
        probs.append(f"real breaks: artifacts {sum(len(g['tests']) for _, g in groups)}, record {c.get('real_break')}")
    n_imp = len(imp["modules"]) if imp else 0
    if n_imp != c.get("import_failure", 0):
        probs.append(f"import failures: artifacts {n_imp}, record {c.get('import_failure')}")
    rec_sigs = {s: n for s, n in (rec.get("top_error_signatures_breaks") or [])}
    if groups and not imp:
        for s, g in groups:
            if s in rec_sigs and rec_sigs[s] != len(g["tests"]):
                probs.append(f"group '{s[:40]}': artifacts {len(g['tests'])}, record {rec_sigs[s]}")
    if probs:
        return [badge("red", "mismatch"), "; ".join(probs)]
    return [badge("green", "consistent"), "break and import-failure counts recomputed from class-*.txt and JUnit equal the record"]


# ---------------------------------------------------------------- citations

class LogIndex:
    """Lines of the run's pytest logs, for citations."""

    def __init__(self, rd: str | None):
        self.rd = rd
        self._cache: dict[str, list[str]] = {}

    def files(self, side: str) -> list[str]:
        if not self.rd:
            return []
        return sorted(os.path.basename(f) for f in glob.glob(os.path.join(self.rd, f"pytest-{side}-*.log")))

    def lines(self, name: str) -> list[str]:
        if name not in self._cache:
            with open(os.path.join(self.rd, name), errors="replace") as fh:
                self._cache[name] = fh.read().splitlines()
        return self._cache[name]

    def find(self, needle: str, sides=("new",)) -> dict | None:
        """First line containing `needle`; pytest `E ` error lines are preferred over echoed source lines."""
        if not needle:
            return None
        for side in sides:
            for f in self.files(side):
                hits = [(i, ln) for i, ln in enumerate(self.lines(f), 1) if needle in ln]
                if hits:
                    hits.sort(key=lambda h: 0 if h[1].lstrip().startswith("E ") else 1)
                    return {"file": f, "line": hits[0][0], "quote": needle}
        return None

    def summary_line(self, side: str = "new", run: int = 1) -> dict | None:
        """pytest's final summary line ('2238 passed, ... in 44.26s') of one run."""
        f = f"pytest-{side}-{run}.log"
        if not self.rd or not os.path.exists(os.path.join(self.rd, f)):
            return None
        pat = re.compile(r"\b\d+ (passed|failed|errors?)\b.* in [\d.]+s")
        lines = self.lines(f)
        for i in range(len(lines), 0, -1):
            m = pat.search(lines[i - 1])
            if m:
                return {"file": f, "line": i, "quote": m.group(0)}
        return None


def search_key(sig: str) -> str:
    """Longest literal fragment of a normalised signature (placeholders N, <path>, 0x? removed), to find it in raw logs."""
    parts = [p.strip(" (:'\"") for p in re.split(r"\bN\b|<path>|0x\?", tidy(sig))]
    parts = [p for p in parts if len(p) >= 6]
    return max(parts, key=len) if parts else ""


def cite_text(cit: dict | None, rel) -> str:
    if not cit:
        return "citation: not found in the run logs"
    return link(f"{cit['file']}:{cit['line']}", rel(cit["file"])) + f" «{cit['quote']}»"


# ---------------------------------------------------------------- claims and verdict

def eval_claims(claims, groups, imp, logs: LogIndex) -> list[dict]:
    """Claim statuses: proven / false / not testable, plus one 'unmentioned change' row per observed change group.
    Status is computed from the evidence, never taken from the claims file. Every row gets a log-line citation."""
    rows = []
    sigs = [s for s, _ in (groups or [])] + ([imp["signature"]] if imp else [])
    covered = {}
    summary_cit = logs.summary_line("new", 1)
    for i, cl in enumerate((claims or {}).get("claims", []), 1):
        cid = cl.get("id") or f"C{i}"
        chk = (cl.get("check") or {}).get("kind", "none")
        if chk == "no_breaks":
            ok = not groups and not imp
            status = "proven" if ok else "false"
            ev = "no test changed result" if ok else (
                f"{sum(len(g['tests']) for _, g in groups or [])} real break(s), {len(imp['modules']) if imp else 0} "
                "import failure(s) observed")
            cit = summary_cit if ok or not sigs else logs.find(search_key(sigs[0]))
        elif chk == "breaks_contain":
            needle = cl["check"]["text"]
            hit = [s for s in sigs if needle in s]
            status = "proven" if hit else "false"
            ev = f"observed: {tidy(hit[0])}" if hit else f"no observed failure contains '{needle}'"
            cit = logs.find(needle) if hit else summary_cit
        else:
            status = "not testable"
            ev = cl.get("why_not_testable") or "a test run of a dependent cannot check this statement directly"
            linked = [s for s in cl.get("explains_signatures", []) if any(s in x for x in sigs)]
            cit = logs.find(linked[0]) if linked else summary_cit
        for s in cl.get("explains_signatures", []):
            covered[s] = (cid, cl.get("link_source", "claims file"))
        rows.append(dict(id=cid, text=cl.get("text", NA), source=cl.get("source", NA), status=status, evidence=ev, citation=cit))
    for s in sigs:
        lk = next(((cid, src) for k, (cid, src) in covered.items() if k in s), None)
        n = next((len(g["tests"]) for gs, g in (groups or []) if gs == s), None)
        what = (f"{n} test(s) now fail with: {tidy(s)}" if n is not None
                else f"{len(imp['modules'])} test module(s) cannot be imported: {tidy(s)}")
        ev = what + (f" (linked to {lk[0]} by {lk[1]})" if lk else " (no claim mentions this)")
        rows.append(dict(id="-", text="Change not in the PR description", source="this run", status="unmentioned change",
                         evidence=ev, citation=logs.find(search_key(s))))
    return rows


def verify_citations(claims_eval: list[dict], rd: str | None) -> Result:
    """Re-check the report's own citations against the log files (the same check used for LLM explanations)."""
    if not claims_eval:
        return Result("report_citations", "skip", "no claim rows in this report")
    if not rd:
        return Result("report_citations", "skip", "run logs not available, so claim rows cannot cite log lines",
                      "Generate the report with --runs-root pointing at the run artifacts.")
    claims = [{"text": f"{x['id']}: {x['evidence']}", "citations": [x["citation"]] if x["citation"] else []} for x in claims_eval]
    res = check_citations(claims, Path(rd))
    return Result("report_citations", res.status, res.detail, res.fix)


def decide(rec: dict, claims_eval: list[dict], golden: list[dict], evals: list[Result], cites: Result) -> dict:
    c = rec.get("classification") or {}
    gates = rec.get("gates") or {}
    req_fail = [k for k, g in gates.items() if g.get("required", True) and not g.get("pass")]
    adv_fail = [k for k, g in gates.items() if not g.get("required", True) and not g.get("pass")]
    eval_fail = [r.check for r in evals if r.status == "fail"]
    eval_warn = [r.check for r in evals if r.status == "warn"]
    rb, imp, fl = c.get("real_break", 0), c.get("import_failure", 0), c.get("flaky", 0)
    false_claims = [x for x in claims_eval if x["status"] == "false"]

    if not rec.get("accepted") or not c or eval_fail:
        verdict, colour, action = "COULD NOT VERIFY", "grey", "Re-run"
        bits = []
        if req_fail or not c or not rec.get("accepted"):
            bits.append(f"required runner check(s) failed: {', '.join(req_fail) or 'record not accepted or not classified'}")
        if eval_fail:
            bits.append(f"eval check(s) failed: {', '.join(eval_fail)}")
        why = "; ".join(bits)
    elif rb or imp or false_claims:
        verdict, colour, action = "NEEDS ATTENTION", "amber", "Reject"
        bits = []
        if rb:
            bits.append(f"{rb} test(s) of the dependent now fail")
        if imp:
            bits.append(f"{imp} test module(s) of the dependent can no longer be imported")
        if false_claims:
            bits.append(f"{len(false_claims)} claim(s) contradicted by the evidence")
        why = "; ".join(bits)
    elif fl or adv_fail or c.get("lost_tests", 0) or eval_warn:
        verdict, colour, action = "VERIFIED", "green", "Approve with notes"
        notes = ([f"{fl} flaky test(s)"] if fl else []) + ([f"advisory check(s) failed: {', '.join(adv_fail)}"] if adv_fail else []) \
            + ([f"{c.get('lost_tests')} lost test(s)"] if c.get("lost_tests", 0) else []) \
            + ([f"eval warning(s): {', '.join(eval_warn)}"] if eval_warn else [])
        why = "no breaks, but see notes: " + ", ".join(notes)
    else:
        verdict, colour, action = "VERIFIED", "green", "Approve"
        why = "no test of the dependent changed result between old and new"

    down = []
    if req_fail or eval_fail:
        conf = "Low"
        down += [f"required check(s) failed ({', '.join(req_fail)})"] if req_fail else []
        down += [f"eval check(s) failed ({', '.join(eval_fail)})"] if eval_fail else []
    else:
        st = rec.get("stability") or {}
        if st.get("old_stable_rate") is None or st.get("new_stable_rate") is None:
            down.append("stability not available")
        elif min(st["old_stable_rate"], st["new_stable_rate"]) < 0.99:
            down.append(f"stability below 0.99 (old {st['old_stable_rate']}, new {st['new_stable_rate']})")
        if fl:
            down.append(f"{fl} flaky test(s)")
        if adv_fail:
            down.append(f"advisory check(s) failed: {', '.join(adv_fail)}")
        if eval_warn:
            down.append(f"eval warning(s): {', '.join(eval_warn)}")
        if "no network" not in str(rec.get("network", "")):
            down.append("tests were not network-isolated")
        known = [g for g in golden if g["ok"] is not None]
        if not known:
            down.append("golden cases not available")
        elif not all(g["ok"] for g in known) or len(known) < len(golden):
            down.append(f"only {sum(1 for g in known if g['ok'])} of {len(golden)} golden cases hold")
        if (rec.get("runs_per_side") or 0) < 3:
            down.append("fewer than 3 runs per side")
        if cites.status == "fail":
            down.append("some report citations could not be verified in the logs")
        elif cites.status == "skip" and claims_eval:
            down.append("run logs not available, so claims could not cite log lines")
        conf = "High" if not down else ("Medium" if len(down) <= 2 else "Low")
    if down:
        conf_reason = "Lowered because: " + "; ".join(down) + "."
    else:
        st = rec["stability"]
        conf_reason = (f"All required checks and evals passed, {rec['runs_per_side']} runs per side gave identical results "
                       f"(stability old {st['old_stable_rate']}, new {st['new_stable_rate']}), "
                       f"{len(golden)} of {len(golden)} golden cases hold, tests ran without network.")
    return dict(verdict=verdict, colour=colour, action=action, why=why, confidence=conf, confidence_reason=conf_reason,
                req_fail=req_fail, adv_fail=adv_fail, eval_fail=eval_fail, eval_warn=eval_warn)


# ---------------------------------------------------------------- rerun command

RUN_DEFAULTS = {"dep_extras": "", "extra_pkgs": "", "override_pins": False, "pytest_args": "", "import_mode": "auto",
                "keep_addopts": False, "workers": "4", "cpus": "", "mem_gb": 6.0, "runs": 3, "test_timeout": 300,
                "run_timeout": 1500, "no_net_isolation": False, "python": "3.13", "subset_note": "", "notes": ""}
RUN_ORDER = ["upstream", "old", "new", "dependent", "dep_version", "dep_extras", "tests", "extra_pkgs", "override_pins",
             "pytest_args", "import_mode", "keep_addopts", "workers", "cpus", "mem_gb", "test_timeout",
             "run_timeout", "no_net_isolation", "python", "expected", "expected_class", "subset_note"]
RUNNER_PATH = "/workspace/blast-radius-research/harness/br_run.py"


def repro_command(args: dict | None, rec: dict) -> str | None:
    """Rerun through this repo's wrapper, which forces 3 runs per side, single-thread env and machine_type."""
    if not args:
        return None
    parts = [f"BR_RUNNER={RUNNER_PATH} python -m harness.run"]
    for k in RUN_ORDER:
        v = args.get(k)
        if v is None or (k in RUN_DEFAULTS and v == RUN_DEFAULTS[k]):
            continue
        flag = "--" + k.replace("_", "-")
        if isinstance(v, bool):
            if v:
                parts.append(flag)
        else:
            parts.append(f"{flag} {shlex.quote(str(v))}")
    parts.append(f"--id {shlex.quote(rec['id'] + '-rerun')}")
    return " \\\n  ".join(parts)


# ---------------------------------------------------------------- build

def _subject(rec: dict, claims: dict | None, pr: dict | None) -> str:
    if get(claims, "subject", "title"):
        return get(claims, "subject", "title")
    if pr:
        return f"{pr['repo']}#{pr['number']}" + (f": {pr['title']}" if pr.get("title") else "")
    return f"{rec.get('upstream')} {rec.get('old_version')} to {rec.get('new_version')}"


def _observed(rec: dict, d: dict, groups, lost) -> str:
    c = rec.get("classification") or {}
    up, ov, nv, dep, dv = (rec.get(k) for k in ("upstream", "old_version", "new_version", "dependent", "dependent_version"))
    rb, ib, ab = c.get("real_break", 0), c.get("import_failure", 0), c.get("already_broken", 0)
    if not rec.get("accepted") or not c or d["eval_fail"]:
        why = ", ".join(d["req_fail"] + d["eval_fail"]) or "record not accepted or not classified"
        obs = f"The run did not pass its own trust checks ({why}), so its results are not usable."
    elif rb or ib:
        bits = []
        if ib:
            bits.append(f"{dep} {dv} can no longer be imported with {up} {nv}: {ib} test module(s) fail to load and {lost} "
                        "test(s) that passed before cannot run")
        if rb:
            kinds = f", in {len(groups)} distinct error type(s)" if groups else ""
            bits.append(f"{rb} test(s) of {dep} that passed with {up} {ov} fail with {up} {nv}{kinds}")
        obs = "; ".join(bits) + f". Same result in all {rec.get('runs_per_side')} runs on each side."
    else:
        tot = get(rec, "stability", "tests")
        obs = (f"No test of {dep} {dv} changed result between {up} {ov} and {nv}"
               + (f" ({tot} tests, {rec.get('runs_per_side')} runs per side)" if tot else "") + ".")
    if ab:
        obs += f" {ab} test(s) already failed before the change and are not counted."
    return obs


def _build_top(rec: dict, rd: str | None, claims: dict | None, golden: list[dict], out_dir: str, runs_root=None,
          require_v1: bool | None = None):
    c = rec.get("classification") or {}
    junit = load_junit(rd)
    groups = break_groups(rd, junit)
    imp = import_group(rec, rd, junit)
    logs = LogIndex(rd)

    def rel(p: str) -> str:
        return os.path.relpath(os.path.join(rd, p), out_dir) if rd else p

    claims_eval = eval_claims(claims, groups, imp, logs)
    cites = verify_citations(claims_eval, rd)
    evals = evaluate_record(rec, runs_root, None, True, require_v1)
    d = decide(rec, claims_eval, golden, evals, cites)
    dep, dv = rec.get("dependent"), rec.get("dependent_version")
    pr = get(claims, "subject", "pr") or rec.get("pr")
    subject = _subject(rec, claims, pr)
    rb, ib, ab, fl, lost = (c.get(k, 0) for k in ("real_break", "import_failure", "already_broken", "flaky", "lost_tests"))
    R = Report()
    now = datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")

    # 1) banner
    R.h(1, f"Reviewer report: {subject}")
    R.p(f"Run `{rec['id']}`, tested against {dep} {dv}. Report generated {now} by reports/generate.py {GENERATOR_VERSION}.", "meta")
    scope = None if pr else ("Scope: this run compares two released versions, not a single PR's commits. "
                             "Any change between the two versions can cause what is shown here.")
    R.banner(d["verdict"], d["action"], d["confidence"], d["confidence_reason"], d["colour"], scope)

    # 2) summary, 3 lines
    R.h(2, "Summary in plain English", "summary")
    says, says_src = get(claims, "says"), get(claims, "says_source")
    line1 = (f"**What it says it does:** {says} ({says_src})." if says
             else "**What it says it does:** not available (no PR or release description was supplied with this run).")
    act = {"Approve": "Approve.", "Approve with notes": "Approve, and read the notes in 'What went wrong'.",
           "Reject": f"Do not approve as is. The change breaks {dep}; see 'What changed in behavior' for what fails.",
           "Re-run": "Do not decide yet. Fix the run problems listed under 'What went wrong' and run again."}[d["action"]]
    R.bullets([line1, f"**What we observed:** {_observed(rec, d, groups, lost)}", f"**What you should do:** {act}"])

    # 3) claims vs reality
    R.h(2, "Claims vs reality", "claims")
    if not claims_eval:
        R.p("Claims: not available (no PR or release description supplied). No behavior change was observed, so there is "
            "nothing unmentioned to flag.")
    else:
        if not claims:
            R.p("Claims: not available (no PR or release description supplied). Every observed change is therefore listed "
                "as unmentioned.")
        R.table(["#", "Claim (source)", "Status", "What we observed", "Log line"],
                [[x["id"], f"{x['text']} ({x['source']})", badge(STATUS_COLOUR[x["status"]], x["status"]), x["evidence"],
                  cite_text(x["citation"], rel)] for x in claims_eval])
        R.p(f"Citation check ({cites.status.upper()}): {cites.detail}")

    # 4) behavior changes
    R.h(2, "What changed in behavior", "changes")
    old_out = rec.get("old_output") or {}
    if groups is None and (rb or ib):
        R.p("Run artifacts not available: counts are from the record. Top error signatures: "
            + ("; ".join(f"{tidy(s)} ({n})" for s, n in (rec.get("top_error_signatures_breaks") or [])[:5]) or NA) + ".")
    elif not groups and not imp:
        R.p("No behavior change: no test went from passing to failing, and every test module still loads.")
    if imp:
        more = f", and {len(imp['modules']) - 8} more" if len(imp["modules"]) > 8 else ""
        before = ", ".join(f"{k}: {v}" for k, v in (get(rec, "dependent_import", "old") or {}).items()) or NA
        R.h(3, f"Import failure: {len(imp['modules'])} test module(s) cannot load")
        R.table(["Item", "Value"], [
            ["Error", tidy(imp["signature"])],
            ["Log line", cite_text(logs.find(search_key(imp["signature"])), rel)],
            ["Before (old)", f"package import: {before}"],
            ["After (new)", "; ".join(f"{k}: {v}" for k, v in imp["package_errors"].items()) or NA],
            ["Tests that passed before and can no longer run", str(len(imp["lost"]))],
            ["Affected modules (first 8)", ", ".join(imp["modules"][:8]) + more],
            ["Full lists", f"{link('class-import_failure.txt', rel('class-import_failure.txt'))}, "
                           f"{link('class-lost_tests.txt', rel('class-lost_tests.txt'))}"],
        ])
    if groups:
        R.p(f"{sum(len(g['tests']) for _, g in groups)} real break(s) in {len(groups)} group(s), largest first.")
        R.table(["#", "Error after the change", "Tests", "Log line"],
                [[str(i), tidy(s), str(len(g["tests"])), cite_text(logs.find(search_key(s)), rel)] for i, (s, g) in enumerate(groups, 1)])
        for i, (s, g) in enumerate(groups, 1):
            ex = g["example"]
            names = [t.split("::", 1)[-1] for t in g["tests"]]
            R.h(3, f"Group {i}: {len(g['tests'])} test(s)")
            R.p(f"**Error:** {tidy(s)}")
            R.p("**Affected tests:** " + ", ".join(f"`{n}`" for n in names[:6]) + (f", and {len(names) - 6} more" if len(names) > 6 else "")
                + f" (full list: {link('class-real_break.txt', rel('class-real_break.txt'))})")
            R.p(f"**Example:** `{ex['test']}`. Before: {', '.join(ex['old'])} (old runs). After: {', '.join(ex['new'])} (new runs).")
            out = e_lines(ex["text"]) or [first_line(ex["message"])]
            prev = old_out.get(ex["test"])
            before_txt = f"Before (old side, from old_output):\n{prev}" if prev else "Before (old side): test passed, no error output"
            R.code(before_txt + "\n\nAfter (new side):\n" + "\n".join(out))
    return R, dict(rec=rec, rd=rd, claims=claims, claims_eval=claims_eval, cites=cites, evals=evals, d=d, pr=pr,
                   subject=subject, groups=groups, imp=imp, rel=rel, golden=golden, says_src=says_src,
                   counts=dict(rb=rb, ib=ib, ab=ab, fl=fl, lost=lost))


def _build_bottom(R: Report, x: dict) -> dict:
    rec, d, evals, cites = x["rec"], x["d"], x["evals"], x["cites"]
    groups, imp, golden, k = x["groups"], x["imp"], x["golden"], x["counts"]
    up, nv, dep = rec.get("upstream"), rec.get("new_version"), rec.get("dependent")
    gates = rec.get("gates") or {}

    # 5) what went right
    R.h(2, "What went right", "right")
    right = [[badge("green", "pass"), GATE_LABELS.get(g, g), v.get("detail", NA)] for g, v in gates.items() if v.get("pass")]
    if rec.get("runs_per_side"):
        right.append([badge("green", "pass") if rec["runs_per_side"] >= 3 else badge("red", "fail"), "Runs per side",
                      f"{rec['runs_per_side']} (minimum 3), alternating old and new"])
    if "no network" in str(rec.get("network", "")):
        right.append([badge("green", "pass"), "Guardrails respected",
                      "tests ran with no network; nothing was posted or filed by the runner"])
    if rec.get("matches_expected") == "yes":
        right.append([badge("green", "pass"), "Matches the prediction written before the run", fmt(rec.get("expected"))])
    n_pass = sum(1 for r in evals if r.status == "pass")
    if n_pass:
        right.append([badge("green", "pass"), "Nathan's evals",
                      f"{n_pass} of {len(evals)} eval checks passed (see 'Evals and guardrails')"])
    if cites.status == "pass":
        right.append([badge("green", "pass"), "Every claim cites a log line", cites.detail])
    R.table(["Status", "Check", "Detail"], right or [[badge("grey", NA), NA, NA]])

    # 6) what went wrong and how to fix it
    R.h(2, "What went wrong and how to fix it", "wrong")
    pr_issues, env_issues = [], []
    if imp:
        pr_issues.append([f"{dep} cannot be imported on the new side ({tidy(imp['signature'])})",
                          f"The change removed or renamed something {dep} uses. Either keep a deprecated alias in {up} for one "
                          f"release, or {dep} must release a fix before this ships."])
    for i, (s, g) in enumerate(groups or [], 1):
        pr_issues.append([f"Group {i}: {len(g['tests'])} test(s) fail with: {tidy(s)}",
                          f"Decide whether this change is intended. If yes, document it as a breaking change and tell {dep}; if "
                          "not, fix it in the PR. Reproduce with the rerun command below and the example test."])
    for c in x["claims_eval"]:
        if c["status"] == "false":
            pr_issues.append([f"Claim {c['id']} is contradicted: {c['text']}",
                              "Correct the PR description or fix the code so the claim holds."])
    for g in d["req_fail"] + d["adv_fail"]:
        env_issues.append([f"Check failed: {GATE_LABELS.get(g, g)} ({get(gates, g, 'detail') or NA})", GATE_FIXES.get(g, NA)])
    for r in evals:
        if r.status in ("fail", "warn"):
            env_issues.append([f"Eval {r.status.upper()}: {r.check} ({r.detail})", r.fix or NA])
    if cites.status == "fail":
        env_issues.append([f"Report citations not verified: {cites.detail}", cites.fix])
    if k["ab"]:
        sig = "; ".join(f"{s} ({n})" for s, n in (rec.get("top_error_signatures_already_broken") or [])[:3]) or NA
        env_issues.append([f"{k['ab']} test(s) of {dep} already fail before the change: {sig}",
                           f"Not caused by this change; ignore for this decision. To clean up the baseline, pin the tool versions "
                           f"{dep} expects or deselect these tests (record it in subset_note)."])
    if k["fl"]:
        env_issues.append([f"{k['fl']} flaky test(s)", GATE_FIXES["stability"]])
    if "no network" not in str(rec.get("network", "")):
        env_issues.append(["Tests were not network-isolated",
                           "Run on a machine where 'unshare -rn true' works, without --no-net-isolation."])
    if rec.get("pin_overridden"):
        env_issues.append([f"{dep}'s declared upper bound on {up} was overridden",
                           f"Results show what would happen if {dep} allowed {up} {nv}; mention this when reporting."])
    if rec.get("subset_note"):
        env_issues.append([f"Only a subset of tests ran: {rec['subset_note']}", "Run the full suite before relying on a VERIFIED verdict."])
    if rec.get("matches_expected") == "no":
        env_issues.append([f"Result differs from the prediction written before the run ({rec.get('expected')})",
                           "Check whether the prediction or the run is wrong; hand-check one example."])
    R.h(3, "Issues in the PR or release")
    if pr_issues:
        R.table(["Issue", "How to fix"], pr_issues)
    else:
        R.p("None found.")
    R.h(3, "Issues in our test environment")
    if env_issues:
        R.table(["Issue", "How to fix"], env_issues)
    else:
        R.p("None found.")

    # 7) trust checks
    R.h(2, "Trust checks", "trust")
    st = rec.get("stability") or {}
    tot = st.get("tests")
    mt = rec.get("machine_type") or {}
    te = rec.get("thread_env") or {}
    req = [g for g, v in gates.items() if v.get("required", True)]
    adv = [g for g in gates if g not in req]
    net_off = "no network" in str(rec.get("network", ""))
    threads_ok = bool(te) and all(v == "1" for v in te.values())
    known = [g for g in golden if g["ok"] is not None]
    g_all = bool(known) and len(known) == len(golden) and all(g["ok"] for g in known)
    golden_badge = badge("green" if g_all else ("grey" if not known else "red"),
                         f"{sum(1 for g in known if g['ok'])} of {len(golden)} hold" if golden else NA)
    golden_note = NA
    if known:
        golden_note = ("checked against the stored golden records (harness " + ", ".join(sorted({str(g["harness"]) for g in known}))
                       + ") with the eval gate's code, not re-run for this report")
        if any(g["run"] == rec["id"] for g in golden):
            golden_note += ". This run is itself one of the golden cases, so this check is partly circular for it"
    gc = rec.get("golden_check")
    fl = k["fl"]
    trust = [
        ["Required checks (gates)", badge("green" if not d["req_fail"] else "red", f"{len(req) - len(d['req_fail'])} of {len(req)} passed"),
         ", ".join(d["req_fail"]) or "all passed"],
        ["Advisory checks", badge("green" if not d["adv_fail"] else "amber", f"{len(adv) - len(d['adv_fail'])} of {len(adv)} passed"),
         ", ".join(d["adv_fail"]) or "all passed"],
        ["Evals (Nathan)", badge("red" if d["eval_fail"] else ("amber" if d["eval_warn"] else "green"), recommendation(evals)),
         ", ".join(d["eval_fail"] + d["eval_warn"]) or "no failures or warnings"],
        ["Golden cases (stored records)", golden_badge, golden_note],
        ["Golden cases (re-run)", badge("green" if gc and gc["passed"] == gc["total"] else ("grey" if not gc else "red"),
                                        f"{gc['passed']} of {gc['total']}" if gc else NA),
         f"re-run with harness {gc['harness_version']} on {gc['date']}" if gc
         else "no golden re-run recorded in this record (golden_check)"],
        ["Report citations", badge(EVAL_COLOUR[cites.status], cites.status), cites.detail],
        ["Flaky rate", badge("green" if (fl == 0 and tot) else ("grey" if not tot else "amber"),
                             f"{fl} of {tot} ({fl / tot:.1%})" if tot else NA),
         f"stability old {fmt(st.get('old_stable_rate'))}, new {fmt(st.get('new_stable_rate'))}"],
        ["Network during tests", badge("green" if net_off else "red", "off" if net_off else "on or unknown"), fmt(rec.get("network"))],
        ["Threads", badge("green" if threads_ok else "amber", "pinned to 1" if threads_ok else (NA if not te else "not all 1")),
         ", ".join(f"{a}={b}" for a, b in te.items()) or NA],
        ["Machine", badge("blue", fmt(mt.get("label") or rec.get("machine"))),
         f"{fmt(mt.get('cpu_model'))}, {fmt(mt.get('cpu_count'))} CPUs, {fmt(mt.get('ram_gb'))} GB RAM, {fmt(mt.get('os'))} "
         f"{fmt(mt.get('arch'))}, CI: {fmt(mt.get('ci'))}"],
        ["Report matches the record", *consistency(rec, groups, imp)],
        ["Prediction before the run", badge({"yes": "green", "no": "red"}.get(rec.get("matches_expected"), "grey"),
                                            fmt(rec.get("matches_expected"))), fmt(rec.get("expected"))],
    ]
    R.table(["Check", "Status", "Detail"], trust)
    if golden:
        R.table(["Golden case", "Status", "Detail"],
                [[g["case"], badge("green" if g["ok"] else ("grey" if g["ok"] is None else "red"),
                                   "holds" if g["ok"] else (NA if g["ok"] is None else "fails")), g["detail"]] for g in golden])

    # 7a) evals and guardrails (Nathan)
    R.h(2, "Evals and guardrails (Nathan)", "evals")
    R.p(f"Independent checks of this record by evals/checks.py and guardrails/schema.py against the shared schema "
        f"`{SCHEMA_ID}` ({schema_reference_note(rec)}). Eval recommendation: **{recommendation(evals)}**. Any FAIL here "
        "makes the verdict COULD NOT VERIFY.")
    R.table(["Check", "Status", "Detail", "How to fix"],
            [[r.check, badge(EVAL_COLOUR[r.status], r.status), r.detail, r.fix or "-"] for r in evals + [cites]])
    return dict(right=right, pr_issues=pr_issues, env_issues=env_issues)


def _build_tail(R: Report, x: dict) -> None:
    rec, rd, rel, pr, k = x["rec"], x["rd"], x["rel"], x["pr"], x["counts"]
    up, ov, nv, dep, dv = (rec.get(f) for f in ("upstream", "old_version", "new_version", "dependent", "dependent_version"))

    # 8) checklist
    R.h(2, "Reviewer checklist", "checklist")
    changed = x["groups"] or x["imp"] or k["rb"] or k["ib"]
    R.checklist([
        "I read the verdict, the recommended action and the confidence.",
        "I checked the claims vs reality table for any 'false' or 'unmentioned change' rows, and opened at least one cited log line.",
        "I looked at the largest behavior-change group and its example error." if changed else "I confirmed there are no behavior changes.",
        "I confirmed the required checks and Nathan's evals passed (Trust checks, Evals and guardrails).",
        "I am satisfied the environment issues (if any) do not change the decision.",
    ])
    dec = rec.get("reviewer_decision")
    if dec:
        R.p(f"**Decision recorded:** {dec['decision'].replace('_', ' ')} by {dec['reviewer']} on {dec['date']}"
            + (f". Note: {dec['note']}" if dec.get("note") else "") + ".", "decision")
    else:
        R.p("**Decision:** ☐ Approve ☐ Approve with notes ☐ Reject ☐ Re-run    Reviewer: ________  Date: ________", "decision")

    # 9) rerun command
    R.h(2, "Rerun command", "repro")
    cmd = repro_command(run_args(rd), rec)
    if cmd:
        R.p("From the blast-radius repo root. The wrapper forces 3 alternating runs per side and the single-thread env, records "
            "machine_type, writes under ./data and never posts anything:")
        R.code(cmd)
    else:
        R.p("Command: not available (args.json missing from the run artifacts).")
    R.p("Needs Linux x86_64, uv 0.12 or newer, git and unshare.")

    # 10) evidence links
    R.h(2, "Evidence links", "evidence")
    ev_rows = []
    if pr:
        name = f"{pr.get('repo')}#{pr.get('number')}"
        ev_rows.append(["PR", link(name, pr["url"]) if pr.get("url") else name])
    if x["says_src"]:
        ev_rows.append(["Where the description comes from", x["says_src"]])
    for c in x["claims_eval"]:
        ev_rows.append([f"Claim {c['id']}" if c["id"] != "-" else "Unmentioned change", cite_text(c["citation"], rel)])
    logs = LogIndex(rd)
    for side in ("old", "new"):
        cit = logs.summary_line(side, 1)
        if cit:
            ev_rows.append([f"pytest summary, {side} side run 1", cite_text(cit, rel)])
    if rec.get("upstream_issue"):
        ev_rows.append(["Upstream issue", fmt(rec.get("upstream_issue"))])
    for pat, what in [("record.json", "Full record"), ("args.json", "Run arguments"), ("setup.log", "Setup log"),
                      ("freeze-old.txt", "Installed packages, old"), ("freeze-new.txt", "Installed packages, new"),
                      ("freeze-diff.txt", "Package difference"), ("pytest-*.log", "pytest logs"), ("junit-*.xml", "JUnit XML"),
                      ("class-*.txt", "Test lists per class")]:
        fs = sorted(glob.glob(os.path.join(rd, pat))) if rd else []
        ev_rows.append([what, ", ".join(link(os.path.basename(f), rel(os.path.basename(f))) for f in fs) if fs else NA])
    R.table(["What", "Link (relative to this report)"], ev_rows)

    # appendix
    R.h(2, "Appendix", "appendix")
    R.h(3, "Commits and versions")
    hc = rec.get("hand_check")
    commits = (f"{fmt(rec.get('upstream_commit_old'))} / {fmt(rec.get('upstream_commit_new'))}"
               if rec.get("upstream_commit_old") or rec.get("upstream_commit_new")
               else (fmt(rec.get("new_direct_url")) if rec.get("new_direct_url") else "PyPI release wheels (no commit recorded)"))
    R.table(["Item", "Value"], [
        ["PR", f"{pr.get('repo')}#{pr.get('number')} ({fmt(pr.get('url'))})" if pr else NA],
        ["PR base / head / merge commit", f"{fmt(pr.get('base_sha') or pr.get('base_commit'))} / {fmt(pr.get('head_sha'))} / "
                                          f"{fmt(pr.get('merge_commit'))}" if pr else NA],
        ["Upstream", f"{up}: old {ov}, new {nv} (requested {fmt(rec.get('new_version_requested'))})"],
        ["Upstream commits (old / new)", commits],
        ["Dependent", f"{dep} {dv}"],
        ["Tests from", f"{fmt(rec.get('test_source'))}; selection: {fmt(rec.get('test_selection'))}"],
        ["Python", fmt(rec.get("python"))],
        ["Environment difference", ", ".join(rec.get("env_diff") or []) or NA],
        ["Runner", f"harness {fmt(rec.get('harness_version'))}, {fmt(rec.get('workers'))} workers, import mode "
                   f"{fmt(rec.get('import_mode'))}, per-test timeout {fmt(rec.get('test_timeout_s'))} s, "
                   f"memory cap {fmt(rec.get('mem_cap_gb'))} GB"],
        ["Record schema", f"v{fmt(rec.get('schema_version'))}; {schema_reference_note(rec)}"],
        ["Run by", f"{fmt(rec.get('who'))} on {fmt(rec.get('machine'))}, {fmt(rec.get('date_ist'))}"],
        ["Hand check", json.dumps(hc) if isinstance(hc, dict) else fmt(hc)],
        ["Upstream issue", fmt(rec.get("upstream_issue"))],
        ["Per-test outcomes", fmt(rec.get("per_test_outcomes"))],
        ["AI explanation", fmt(get(rec, "explanation", "status"))],
    ])
    R.h(3, "Timings")
    du = rec.get("duration_s") or {}
    R.p(f"Total wall time {fmt(du.get('total_wall'))} s; mean test time old {fmt(du.get('tests_old_mean'))} s, "
        f"new {fmt(du.get('tests_new_mean'))} s.")
    R.table(["Side", "Run", "Exit", "Seconds", "pytest summary"],
            [[p["side"], str(p["run"]), str(p.get("exit")), str(p.get("seconds", NA)), p.get("pytest_summary") or NA]
             for p in rec.get("per_run", [])])
    R.h(2, "Glossary", "glossary")
    R.table(["Term", "Meaning"], [[a, b] for a, b in GLOSSARY])


def build(rec: dict, rd: str | None, claims: dict | None, golden: list[dict], out_dir: str, runs_root=None,
          require_v1: bool | None = None):
    """Build the report blocks and a one-row summary for the daily summary."""
    R, x = _build_top(rec, rd, claims, golden, out_dir, runs_root, require_v1)
    _build_bottom(R, x)
    _build_tail(R, x)
    d, k = x["d"], x["counts"]
    summary = dict(id=rec["id"], subject=x["subject"], dependent=f"{rec.get('dependent')} {rec.get('dependent_version')}",
                   verdict=d["verdict"], action=d["action"], confidence=d["confidence"], colour=d["colour"], why=d["why"],
                   date=rec.get("date_ist"), real_break=k["rb"], import_failure=k["ib"], flaky=k["fl"],
                   evals=recommendation(x["evals"]), citations=x["cites"].status,
                   claims=[{"id": c["id"], "status": c["status"], "citation": c["citation"]} for c in x["claims_eval"]])
    return R, summary


# ---------------------------------------------------------------- renderers

def md_cell(v) -> str:
    if isinstance(v, tuple) and v[0] == "badge":
        return f"{EMOJI.get(v[1], '')} **{v[2]}**"
    return str(v).replace("|", "\\|").replace("\n", " ")


def to_md(R: Report) -> str:
    out = []
    for b in R.blocks:
        k = b[0]
        if k == "h":
            out.append("#" * b[1] + " " + b[2] + "\n")
        elif k == "p":
            out.append(b[1] + "\n")
        elif k == "ul":
            out.append("\n".join(f"- {x}" for x in b[1]) + "\n")
        elif k == "check":
            out.append("\n".join(f"- [ ] {x}" for x in b[1]) + "\n")
        elif k == "code":
            out.append("```\n" + b[1] + "\n```\n")
        elif k == "table":
            out.append("| " + " | ".join(b[1]) + " |\n|" + "---|" * len(b[1]) + "\n"
                       + "\n".join("| " + " | ".join(md_cell(c) for c in r) + " |" for r in b[2]) + "\n")
        elif k == "banner":
            _, v, a, c, why, col, scope = b
            out.append(f"> ## {EMOJI[col]} {v}\n>\n> **Recommended action:** {a}  \n> **Confidence:** {c}. {why}\n"
                       + (f">\n> {scope}\n" if scope else ""))
    return "\n".join(out)


def inline(s) -> str:
    s = html.escape(str(s), quote=False)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r"<a href='\2'>\1</a>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


CSS = """
:root{--green:#1e7e34;--green-bg:#e6f4ea;--amber:#9a5b00;--amber-bg:#fff4e0;--red:#b3261e;--red-bg:#fdecea;
--grey:#555;--grey-bg:#eef0f2;--blue:#1a5fb4;--blue-bg:#e8f0fc;--ink:#1f2328;--line:#d0d7de}
*{box-sizing:border-box}body{font:14px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);
max-width:1000px;margin:24px auto;padding:0 24px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;border-bottom:2px solid var(--line);padding-bottom:4px;margin-top:28px}
h3{font-size:15px;margin:18px 0 6px}p.meta{color:#57606a;margin-top:0;font-size:12px}
table{border-collapse:collapse;width:100%;margin:8px 0 12px;font-size:12.5px}
th,td{border:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
th{background:#f6f8fa}tr:nth-child(even) td{background:#fbfbfc}
code{font:12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#f3f4f6;padding:1px 4px;border-radius:3px}
pre{font:11.5px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#f6f8fa;border:1px solid var(--line);
padding:10px;border-radius:6px;white-space:pre-wrap;word-break:break-all}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-weight:600;font-size:11.5px;white-space:nowrap}
.b-green{color:var(--green);background:var(--green-bg)}.b-amber{color:var(--amber);background:var(--amber-bg)}
.b-red{color:var(--red);background:var(--red-bg)}
.b-grey{color:var(--grey);background:var(--grey-bg)}.b-blue{color:var(--blue);background:var(--blue-bg)}
.banner{border-radius:10px;padding:14px 18px;margin:14px 0 6px;border:2px solid}
.banner .v{font-size:24px;font-weight:800;letter-spacing:.5px}.banner .row{margin-top:6px;font-size:14px}
.banner.green{border-color:var(--green);background:var(--green-bg)}.banner.green .v{color:var(--green)}
.banner.amber{border-color:var(--amber);background:var(--amber-bg)}.banner.amber .v{color:var(--amber)}
.banner.red{border-color:var(--red);background:var(--red-bg)}.banner.red .v{color:var(--red)}
.banner.grey{border-color:var(--grey);background:var(--grey-bg)}.banner.grey .v{color:var(--grey)}
.action{display:inline-block;font-weight:700;padding:2px 10px;border-radius:6px;background:#fff;border:1px solid var(--line)}
.scope{font-size:12.5px;color:#57606a;margin-top:6px}
ul.check{list-style:none;padding-left:4px}ul.check li:before{content:"\\2610  ";font-size:16px}
p.decision{border:1px dashed #8c959f;padding:10px;border-radius:6px;font-size:14px}
@page{size:A4;margin:14mm 12mm}
@media print{body{margin:0;max-width:none;padding:0}h2{break-after:avoid}pre,.banner{break-inside:avoid}tr{break-inside:avoid}
thead{display:table-header-group}}
"""


def html_cell(v) -> str:
    if isinstance(v, tuple) and v[0] == "badge":
        return f'<span class="badge b-{v[1]}">{html.escape(v[2])}</span>'
    return inline(v)


def to_html(R: Report, title: str) -> str:
    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
           f"<style>{CSS}</style></head><body>"]
    for b in R.blocks:
        k = b[0]
        if k == "h":
            anchor = f' id="{b[3]}"' if b[3] else ""
            out.append(f"<h{b[1]}{anchor}>{inline(b[2])}</h{b[1]}>")
        elif k == "p":
            cls = f' class="{b[2]}"' if b[2] else ""
            out.append(f"<p{cls}>{inline(b[1])}</p>")
        elif k == "ul":
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in b[1]) + "</ul>")
        elif k == "check":
            out.append("<ul class='check'>" + "".join(f"<li>{inline(x)}</li>" for x in b[1]) + "</ul>")
        elif k == "code":
            out.append(f"<pre>{html.escape(b[1])}</pre>")
        elif k == "table":
            out.append("<table><thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in b[1]) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{html_cell(c)}</td>" for c in r) + "</tr>" for r in b[2])
                       + "</tbody></table>")
        elif k == "banner":
            _, v, a, c, why, col, scope = b
            out.append(f"<div class='banner {col}'><div class='v'>{html.escape(v)}</div>"
                       f"<div class='row'>Recommended action: <span class='action badge b-{ACTION_COLOUR.get(a, 'grey')}'>"
                       f"{html.escape(a)}</span> &nbsp; Confidence: <strong>{html.escape(c)}</strong></div>"
                       f"<div class='row'>{inline(why)}</div>"
                       + (f"<div class='scope'>{inline(scope)}</div>" if scope else "") + "</div>")
    out.append("</body></html>")
    return "\n".join(out)


def find_chrome() -> str | None:
    for name in (os.environ.get("BR_CHROME"), "google-chrome", "chromium", "chromium-browser"):
        if name and shutil.which(name):
            return shutil.which(name)
    return None


def to_pdf(html_path: str, pdf_path: str) -> str | None:
    """Print HTML to A4 PDF with headless Chrome/Chromium. Returns None on success, else an error string."""
    chrome = find_chrome()
    if not chrome:
        return "no chrome/chromium on PATH (set BR_CHROME); PDF not generated"
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
    with tempfile.TemporaryDirectory() as prof:
        r = subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", f"--user-data-dir={prof}",
                            "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", "file://" + os.path.abspath(html_path)],
                           capture_output=True, text=True, timeout=180)
    ok = os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0
    return None if ok else f"chrome failed: {r.stderr[-300:]}"


# ---------------------------------------------------------------- daily summary

def sort_summaries(summaries: list[dict]) -> list[dict]:
    """Needs-attention items first (spec order), then by id."""
    return sorted(summaries, key=lambda s: (ORDER.get((s["verdict"], s["action"]), 9), s["id"]))


def write_summary(summaries: list[dict], out_dir: str, title: str, formats) -> str | None:
    s = sort_summaries(summaries)
    R = Report()
    R.h(1, title)

    def n(v):
        return sum(1 for x in s if x["verdict"] == v)

    R.p(f"Generated {datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')}. {len(s)} report(s): "
        f"{n('NEEDS ATTENTION')} need attention, {n('COULD NOT VERIFY')} could not be verified, {n('VERIFIED')} verified. "
        "Items that need a decision are listed first.", "meta")
    need = [x for x in s if (x["verdict"], x["action"]) != ("VERIFIED", "Approve")]
    R.h(2, "Needs attention first")
    if need:
        R.bullets([f"**{x['verdict']} / {x['action']}** ({x['confidence']} confidence): {x['subject']}, tested against "
                   f"{x['dependent']}. {x['why'][0].upper() + x['why'][1:]}. "
                   + link("Open report", f"{x['id']}/REPORT.html") + " (" + link("PDF", f"{x['id']}/REPORT.pdf") + ")"
                   for x in need])
    else:
        R.p("Nothing needs attention: every report is VERIFIED / Approve.")
    R.h(2, "All reports")
    R.table(["Verdict", "Action", "Confidence", "Subject", "Tested against", "Why", "Evals", "Report"],
            [[badge(x["colour"], x["verdict"]), badge(ACTION_COLOUR.get(x["action"], "grey"), x["action"]), x["confidence"],
              x["subject"], x["dependent"], x["why"], badge("green" if x["evals"] == "APPROVE" else "red", x["evals"]),
              link("HTML", f"{x['id']}/REPORT.html") + " · " + link("PDF", f"{x['id']}/REPORT.pdf") + " · "
              + link("MD", f"{x['id']}/REPORT.md")] for x in s])
    R.h(2, "Verdict meanings")
    R.table(["Verdict", "Meaning"], [
        [badge("amber", "NEEDS ATTENTION"), "The run is trustworthy and found a problem: breaks, import failures, or a false claim."],
        [badge("grey", "COULD NOT VERIFY"), "The run failed its own trust checks or Nathan's evals. No conclusion; re-run after fixing."],
        [badge("green", "VERIFIED"), "The run is trustworthy and found no behavior change."]])
    os.makedirs(out_dir, exist_ok=True)
    if "md" in formats:
        Path(out_dir, "SUMMARY.md").write_text(to_md(R))
    hp = os.path.join(out_dir, "SUMMARY.html")
    Path(hp).write_text(to_html(R, title))
    return to_pdf(hp, os.path.join(out_dir, "SUMMARY.pdf")) if "pdf" in formats else None


def render_record(rec: dict, out_dir: str, runs_root=None, record_path=None, claims_path=None, golden=None,
                  formats=("md", "html", "pdf"), require_v1: bool | None = None) -> dict:
    """Write REPORT.md/.html/.pdf for one record into out_dir; return its summary row."""
    rd = resolve_run_dir(rec, runs_root, record_path)
    claims = load_claims(rec, claims_path)
    golden = golden_status(load_records_file(GOLDEN_RECORDS)) if golden is None else golden
    os.makedirs(out_dir, exist_ok=True)
    R, summary = build(rec, rd, claims, golden, out_dir, runs_root, require_v1)
    if "md" in formats:
        Path(out_dir, "REPORT.md").write_text(to_md(R))
    hp = os.path.join(out_dir, "REPORT.html")
    Path(hp).write_text(to_html(R, f"Reviewer report {rec['id']}"))
    summary["pdf_error"] = to_pdf(hp, os.path.join(out_dir, "REPORT.pdf")) if "pdf" in formats else None
    summary["run_dir"] = rd
    return summary
