#!/usr/bin/env python3
"""Reviewer report generator for Proof-of-Change / Blast Radius runs.

Input : one observation record (record.json) plus its run directory (junit, logs, freeze, class-*.txt),
        optionally a claims file (what the PR or release says it does) and the golden case files.
Output: REPORT.md, REPORT.html (self-contained, printable) and REPORT.pdf (via headless Chrome).

Rule: every number comes from the record or the run artifacts. Anything missing is printed as "not available".
Standard library only (PDF needs google-chrome or chromium on PATH).
"""
import argparse, datetime, glob, html, json, os, re, shlex, shutil, subprocess, sys, tempfile
import xml.etree.ElementTree as ET

GENERATOR_VERSION = "0.1"
NA = "not available"
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# Fallback copy of harness/brlib.py FIXES, used when brlib is not importable (e.g. in the team repo).
DEFAULT_FIXES = {'env_identical_except_upstream': 'freeze-diff.txt shows more than the upstream line. Usually the new '
                                  'upstream pulled in a dependency. Rerun; if it persists, add the '
                                  'dependency pin to --extra-pkgs so both sides get it.',
 'no_secrets_in_logs': 'Credential-like strings were found and redacted. Find where they entered the '
                       'environment and remove them before the next run.',
 'old_side_healthy': 'The OLD side did not run cleanly (no tests passed, or collection errors). Usually a '
                     'missing test dependency or the wrong test path. Read the collection errors in '
                     'pytest-old-1.log, add the missing packages with --extra-pkgs or fix --tests, then '
                     'rerun. Results from this run are not trustworthy.',
 'runs_complete': 'A side has fewer than the required runs or a run produced no JUnit XML. Look at the '
                  'pytest-<side>-<n>.log tail; if it timed out, raise --run-timeout or choose a smaller '
                  'documented subset, then rerun.',
 'schema_valid': 'The record does not match harness/schema/observation.schema.json. Fix the harness (this is '
                 'a bug), then rerun.',
 'stability': 'Outcomes changed between runs on the same side. List the tests in class-flaky.txt, rerun them '
              'alone with -p no:randomly, and exclude confirmed flaky tests with --deselect (document it in '
              'subset_note).',
 'threads_pinned': 'The thread variables were not 1 inside the test process. Do not override '
                   'OMP/MKL/OPENBLAS_NUM_THREADS; rerun.',
 'venv_isolated': "A venv can see system site-packages. Recreate it with 'uv venv' (never "
                  '--system-site-packages) and rerun.',
 'versions_verified': 'The installed versions in freeze-old.txt / freeze-new.txt do not match the request. '
                      'Check setup.log for resolver messages; pin the dependent with --dep-version and '
                      'rerun.'}


# ---------------------------------------------------------------- helpers

def normalise(msg):
    """Same normalisation as harness/br_run.py signature(), so groups line up with the record."""
    msg = re.sub(r"^(E\s+)+", "", (msg or "").strip())
    s = re.sub(r"0x[0-9a-fA-F]+", "0x?", msg)
    s = re.sub(r"(/[\w.-]+)+/(site-packages|runs)/[^\s'\"]*", "<path>", s)
    s = re.sub(r"\b\d+(\.\d+)?\b", "N", s)
    return s[:160]


def tidy(sig):
    """Display form of a signature: drop a dangling '(<path>' left by path normalisation."""
    return re.sub(r"\s*\(<path>$", "", sig or "")


def first_line(msg):
    for l in (msg or "").splitlines():
        if l.strip():
            return l.strip()
    return ""


def e_lines(text, n=8):
    """The 'E ' lines of a pytest traceback (the actual error output), last n of them."""
    ls = [l.strip()[1:].strip() for l in (text or "").splitlines() if l.strip().startswith("E ")]
    seen, uniq = set(), []
    for l in ls:
        if l and l not in seen:
            seen.add(l); uniq.append(l)
    return uniq[-n:]


def get(d, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d or d[p] is None:
            return default
        d = d[p]
    return d


def fmt(v):
    return NA if v is None or v == "" else v


def read_lines(p):
    if not os.path.exists(p):
        return None
    return [l.strip() for l in open(p) if l.strip()]


def parse_junit(path):
    """test id -> (outcome, message, text). outcome in passed/failed/error/skipped."""
    out = {}
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return None
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


# ---------------------------------------------------------------- model

class Report:
    """Builds a format-neutral list of blocks; md and html renderers turn it into text."""

    def __init__(self):
        self.blocks = []

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


# status badge = ("badge", colour, text). colours: green, amber, red, grey, blue
def badge(colour, text):
    return ("badge", colour, text)


EMOJI = {"green": "🟢", "amber": "🟠", "red": "🔴", "grey": "⚪", "blue": "🔵"}

GLOSSARY = [
    ("Old side / new side", "The same dependent library tested twice: once with the old version of the upstream library, once with the new one. Nothing else differs."),
    ("Upstream", "The library being changed (for example pandas). The PR or release under review belongs to it."),
    ("Dependent", "A library that uses the upstream. Its own tests are our test subject."),
    ("Real break", "A test that passed in every old run and failed in every new run. This is a behavior change caused by the upstream change."),
    ("Import failure", "A test module that cannot even be loaded on the new side, so none of its tests can run. Counted per module."),
    ("Lost tests", "Tests that passed before but could not run after, because their module failed to load. Not counted as real breaks."),
    ("Already broken", "Tests that failed before the change too. Not caused by the change."),
    ("Flaky", "Tests whose result changes between runs on the same side. They are not trusted either way."),
    ("Error signature", "The error message with numbers and file paths removed, so identical failures group together."),
    ("Gate", "An automatic check that the run itself is trustworthy (right versions, same environment, enough runs). Required gates must pass for the result to count."),
    ("Golden case", "A known example with a known answer. If the tool still gets the golden cases right, its answers on new cases are more believable."),
    ("Stability", "Share of tests that gave the same result in every run on one side. 1.0 means fully repeatable."),
    ("JUnit XML", "The machine-readable test result file pytest writes for each run."),
    ("Freeze", "The exact list of installed packages and versions on each side."),
]


# ---------------------------------------------------------------- analysis

def load_inputs(record_path, root, claims_path=None, golden_dir=None, obs_path=None):
    rec = json.load(open(record_path))
    rd = os.path.join(root, rec.get("logs") or os.path.dirname(record_path))
    if not os.path.isdir(rd):
        rd = os.path.dirname(os.path.abspath(record_path))
    claims = json.load(open(claims_path)) if claims_path and os.path.exists(claims_path) else None
    args = json.load(open(os.path.join(rd, "args.json"))) if os.path.exists(os.path.join(rd, "args.json")) else None
    junit = {}
    for f in sorted(glob.glob(os.path.join(rd, "junit-*-*.xml"))):
        m = re.match(r"junit-(old|new)-(\d+)\.xml", os.path.basename(f))
        if m:
            junit[(m.group(1), int(m.group(2)))] = parse_junit(f)
    golden = []
    if golden_dir and os.path.isdir(golden_dir):
        obs = {}
        if obs_path and os.path.exists(obs_path):
            for l in open(obs_path):
                if l.strip():
                    r = json.loads(l)
                    obs[r["id"]] = r
        for gf in sorted(glob.glob(os.path.join(golden_dir, "*.json"))):
            golden.append(check_golden(json.load(open(gf)), obs, os.path.basename(gf)))
    return rec, rd, claims, args, junit, golden


def check_golden(g, obs, fname):
    """Re-check a golden case's assertions against its stored record (no re-run)."""
    rid = g.get("source_run")
    r = obs.get(rid)
    res = {"case": g.get("case", fname), "file": fname, "run": rid, "harness": get(r, "harness_version") if r else None}
    if not r:
        res.update(ok=None, detail="source record not found in observations.jsonl")
        return res
    a, problems = g.get("assert", {}), []
    if "accepted" in a and r.get("accepted") != a["accepted"]:
        problems.append("accepted differs")
    for k, v in (a.get("classification_exact") or {}).items():
        if (r.get("classification") or {}).get(k) != v:
            problems.append(f"{k} is {(r.get('classification') or {}).get(k)}, expected {v}")
    side_keys = {"old_summary_passed_every_run": ("old", "passed"), "new_summary_passed_every_run": ("new", "passed"),
                 "new_summary_errors_every_run": ("new", "error")}
    for k, (side, field) in side_keys.items():
        if k in a:
            vals = [p.get("summary_counts", {}).get(field, 0) for p in r["per_run"] if p["side"] == side]
            if any(v != a[k] for v in vals):
                problems.append(f"{side} {field} {vals}, expected {a[k]}")
    sig = a.get("import_failure_signature_contains") or a.get("top_break_signature_contains")
    if sig and not any(sig in s for s, _ in (r.get("top_error_signatures_breaks") or [])):
        problems.append(f"signature '{sig}' not found")
    res.update(ok=not problems, detail="; ".join(problems) or "all assertions hold")
    return res


def outcomes(junit, tid, side):
    runs = sorted(n for (s, n) in junit if s == side)
    res = []
    for n in runs:
        j = junit[(side, n)] or {}
        res.append(j.get(tid, ("absent", "", ""))[0])
    return res


def break_groups(rec, rd, junit):
    """Group real breaks by normalised error signature, from class-real_break.txt + new-side JUnit."""
    tests = read_lines(os.path.join(rd, "class-real_break.txt"))
    if tests is None:
        return None
    groups = {}
    first_new = min((n for (s, n) in junit if s == "new"), default=None)
    for t in tests:
        oc, msg, txt = (junit.get(("new", first_new)) or {}).get(t, ("absent", "", "")) if first_new else ("absent", "", "")
        sig = normalise(first_line(msg)) or "(no message in JUnit)"
        g = groups.setdefault(sig, {"tests": [], "example": None})
        g["tests"].append(t)
        if g["example"] is None:
            g["example"] = {"test": t, "message": msg, "text": txt,
                            "old": outcomes(junit, t, "old"), "new": outcomes(junit, t, "new")}
    return sorted(groups.items(), key=lambda kv: -len(kv[1]["tests"]))


def import_group(rec, rd, junit):
    mods = read_lines(os.path.join(rd, "class-import_failure.txt"))
    if not mods:
        return None
    new_imp = get(rec, "dependent_import", "new") or {}
    bad = {k: v for k, v in new_imp.items() if v != "ok"}
    sig = normalise(next(iter(bad.values()))) if bad else None
    if not sig:  # fall back to the first collection error in new JUnit
        for (s, n), j in sorted(junit.items()):
            if s == "new" and j:
                for t, (oc, msg, txt) in j.items():
                    if oc == "error":
                        sig = normalise(e_lines(txt, 1)[0] if e_lines(txt, 1) else first_line(msg))
                        break
            if sig:
                break
    return {"modules": mods, "signature": sig or NA, "package_errors": bad,
            "lost": read_lines(os.path.join(rd, "class-lost_tests.txt")) or []}


def consistency(rec, groups, imp):
    """Cross-check: counts recomputed from the artifacts must equal the record's classification."""
    c = rec.get("classification") or {}
    probs = []
    if groups is not None and sum(len(g["tests"]) for _, g in groups) != c.get("real_break", 0):
        probs.append(f"real breaks: artifacts {sum(len(g['tests']) for _, g in groups)}, record {c.get('real_break')}")
    if groups is None and c.get("real_break"):
        probs.append("class-real_break.txt missing")
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


def decide(rec, claims_eval, golden):
    c = rec.get("classification") or {}
    gates = rec.get("gates") or {}
    req_fail = [k for k, g in gates.items() if g.get("required", True) and not g.get("pass")]
    adv_fail = [k for k, g in gates.items() if not g.get("required", True) and not g.get("pass")]
    rb, imp, fl = c.get("real_break", 0), c.get("import_failure", 0), c.get("flaky", 0)
    false_claims = [x for x in claims_eval if x["status"] == "false"]

    if not rec.get("accepted") or not c:
        verdict, colour = "COULD NOT VERIFY", "grey"
        action = "Re-run"
        why = f"required check(s) failed: {', '.join(req_fail) or 'no classification in record'}"
    elif rb or imp or false_claims:
        verdict, colour, action = "NEEDS ATTENTION", "amber", "Reject"
        bits = []
        if rb: bits.append(f"{rb} test(s) of the dependent now fail")
        if imp: bits.append(f"{imp} test module(s) of the dependent can no longer be imported")
        if false_claims: bits.append(f"{len(false_claims)} claim(s) contradicted by the evidence")
        why = "; ".join(bits)
    elif fl or adv_fail or c.get("lost_tests", 0):
        verdict, colour, action = "VERIFIED", "green", "Approve with notes"
        why = "no breaks, but see notes: " + ", ".join(
            [f"{fl} flaky test(s)"] * bool(fl) + [f"advisory check(s) failed: {', '.join(adv_fail)}"] * bool(adv_fail)
            + [f"{c.get('lost_tests')} lost test(s)"] * bool(c.get("lost_tests", 0)))
    else:
        verdict, colour, action = "VERIFIED", "green", "Approve"
        why = "no test of the dependent changed result between old and new"

    # confidence
    reasons_down = []
    if req_fail:
        conf = "Low"
        reasons_down.append(f"required check(s) failed ({', '.join(req_fail)})")
    else:
        st = rec.get("stability") or {}
        if st.get("old_stable_rate") is None or st.get("new_stable_rate") is None:
            reasons_down.append("stability not available")
        elif min(st["old_stable_rate"], st["new_stable_rate"]) < 0.99:
            reasons_down.append(f"stability below 0.99 (old {st['old_stable_rate']}, new {st['new_stable_rate']})")
        if fl:
            reasons_down.append(f"{fl} flaky test(s)")
        if adv_fail:
            reasons_down.append(f"advisory check(s) failed: {', '.join(adv_fail)}")
        if "no network" not in str(rec.get("network", "")):
            reasons_down.append("tests were not network-isolated")
        gok = [g for g in golden if g["ok"]]
        if not golden:
            reasons_down.append("golden cases not available")
        elif len(gok) < len(golden):
            reasons_down.append(f"only {len(gok)} of {len(golden)} golden cases hold")
        if rec.get("runs_per_side", 0) < 3:
            reasons_down.append("fewer than 3 runs per side")
        conf = "High" if not reasons_down else ("Medium" if len(reasons_down) <= 2 else "Low")
    if reasons_down:
        conf_reason = "Lowered because: " + "; ".join(reasons_down)
    else:
        st = rec["stability"]
        conf_reason = (f"All required checks passed, {rec['runs_per_side']} runs per side gave identical results "
                       f"(stability old {st['old_stable_rate']}, new {st['new_stable_rate']}), "
                       f"{len(golden)} of {len(golden)} golden cases hold, tests ran without network.")
    return dict(verdict=verdict, colour=colour, action=action, why=why, confidence=conf,
                confidence_reason=conf_reason, req_fail=req_fail, adv_fail=adv_fail)


def eval_claims(claims, groups, imp):
    """Claim statuses: proven / false / not testable, plus one 'unmentioned change' per observed change group
    that no claim covers. Status is computed from the evidence, never taken from the claims file."""
    rows = []
    sigs = [s for s, _ in (groups or [])] + ([imp["signature"]] if imp else [])
    covered = {}
    for i, cl in enumerate((claims or {}).get("claims", []), 1):
        cid = cl.get("id") or f"C{i}"
        chk = (cl.get("check") or {}).get("kind", "none")
        if chk == "no_breaks":
            ok = not groups and not imp
            status = "proven" if ok else "false"
            ev = "no test changed result" if ok else f"{sum(len(g['tests']) for _, g in groups or [])} real break(s), {len(imp['modules']) if imp else 0} import failure(s) observed"
        elif chk == "breaks_contain":
            needle = cl["check"]["text"]
            hit = [s for s in sigs if needle in s]
            status = "proven" if hit else "false"
            ev = f"observed: {hit[0]}" if hit else f"no observed failure contains '{needle}'"
        else:
            status, ev = "not testable", cl.get("why_not_testable") or "a test run of a dependent cannot check this statement directly"
        for s in cl.get("explains_signatures", []):
            covered[s] = (cid, cl.get("link_source", "claims file"))
        rows.append(dict(id=cid, text=cl.get("text", NA), source=cl.get("source", NA), status=status, evidence=ev))
    for s in sigs:
        link = next(((cid, src) for k, (cid, src) in covered.items() if k in s), None)
        n = next((len(g["tests"]) for gs, g in (groups or []) if gs == s), None)
        what = f"{n} test(s) now fail with: {tidy(s)}" if n is not None else f"{len(imp['modules'])} test module(s) cannot be imported: {tidy(s)}"
        ev = what + (f" (linked to {link[0]} by {link[1]})" if link else " (no claim mentions this)")
        rows.append(dict(id="-", text="Change not in the PR description", source="this run",
                         status="unmentioned change", evidence=ev))
    return rows


STATUS_COLOUR = {"proven": "green", "false": "red", "unmentioned change": "amber", "not testable": "grey"}


# ---------------------------------------------------------------- reproduce command

def repro_command(args, rec):
    if not args:
        return None
    defaults = {"dep_extras": "", "extra_pkgs": "", "override_pins": False, "pytest_args": "", "import_mode": "auto",
                "keep_addopts": False, "workers": "4", "cpus": "", "mem_gb": 6.0, "runs": 3, "test_timeout": 300,
                "run_timeout": 1500, "no_net_isolation": False, "python": "3.13", "subset_note": "", "notes": ""}
    order = ["upstream", "old", "new", "dependent", "dep_version", "dep_extras", "tests", "extra_pkgs", "override_pins",
             "pytest_args", "import_mode", "keep_addopts", "workers", "cpus", "mem_gb", "runs", "test_timeout",
             "run_timeout", "no_net_isolation", "python", "expected", "expected_class", "subset_note"]
    parts = ["python3 harness/br_run.py"]
    for k in order:
        if k not in args or args[k] is None:
            continue
        v = args[k]
        if k in defaults and v == defaults[k]:
            continue
        flag = "--" + k.replace("_", "-")
        if isinstance(v, bool):
            if v:
                parts.append(flag)
        else:
            parts.append(f"{flag} {shlex.quote(str(v))}")
    parts.append(f"--id {shlex.quote(rec['id'] + '-rerun')}")
    return "cd /workspace/blast-radius-research && \\\n  " + " \\\n  ".join(parts)


# ---------------------------------------------------------------- build

def build(rec, rd, claims, args, junit, golden, out_dir, root):
    c = rec.get("classification") or {}
    groups = break_groups(rec, rd, junit)
    imp = import_group(rec, rd, junit)
    claims_eval = eval_claims(claims, groups, imp)
    d = decide(rec, claims_eval, golden)
    rel = lambda p: os.path.relpath(os.path.join(rd, p), out_dir)
    up, ov, nv = rec.get("upstream"), rec.get("old_version"), rec.get("new_version")
    dep, dv = rec.get("dependent"), rec.get("dependent_version")
    pr = get(claims, "subject", "pr")
    subject = get(claims, "subject", "title") or f"{up} {ov} to {nv}"
    R = Report()
    now = datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
    R.h(1, f"Reviewer report: {subject}")
    R.p(f"Run `{rec['id']}`, tested against {dep} {dv}. Report generated {now} by render_report.py {GENERATOR_VERSION}.", "meta")

    scope = None
    if not pr:
        scope = ("Scope: this run compares two released versions, not a single PR's commits. "
                 "Any change between the two versions can cause what is shown here.")
    R.banner(d["verdict"], d["action"], d["confidence"], d["confidence_reason"], d["colour"], scope)

    # 2) summary
    R.h(2, "Summary in plain English", "summary")
    says = get(claims, "says")
    says_src = get(claims, "says_source")
    line1 = f"**What it says it does:** {says} ({says_src})." if says else "**What it says it does:** not available (no PR or release description was supplied with this run)."
    rb, ib, ab, fl, lost = (c.get(k, 0) for k in ("real_break", "import_failure", "already_broken", "flaky", "lost_tests"))
    if not rec.get("accepted"):
        obs = f"The run did not pass its own trust checks ({', '.join(d['req_fail'])}), so its results are not usable."
    elif rb or ib:
        bits = []
        if ib:
            bits.append(f"{dep} {dv} can no longer be imported with {up} {nv}: {ib} test module(s) fail to load and {lost} test(s) that passed before cannot run")
        if rb:
            bits.append(f"{rb} test(s) of {dep} that passed with {up} {ov} fail with {up} {nv}, in {len(groups or [])} distinct error type(s)")
        obs = "; ".join(bits) + f". Same result in all {rec.get('runs_per_side')} runs on each side."
    else:
        tot = get(rec, "stability", "tests")
        obs = (f"No test of {dep} {dv} changed result between {up} {ov} and {nv}"
               + (f" ({tot} tests, {rec.get('runs_per_side')} runs per side)" if tot else "") + ".")
    if ab:
        obs += f" {ab} test(s) already failed before the change and are not counted."
    act = {"Approve": "Approve.", "Approve with notes": "Approve, and read the notes in 'What went wrong'.",
           "Reject": f"Do not approve as is. The change breaks {dep}; see 'What changed in behavior' for what fails.",
           "Re-run": "Do not decide yet. Fix the run problems listed under 'What went wrong' and run again."}[d["action"]]
    R.bullets([line1, f"**What we observed:** {obs}", f"**What you should do:** {act}"])

    # 3) claims vs reality
    R.h(2, "Claims vs reality", "claims")
    if not claims_eval:
        R.p("Claims: not available (no PR or release description supplied). No behavior change was observed, so there is nothing unmentioned to flag.")
    else:
        if not claims:
            R.p("Claims: not available (no PR or release description supplied). Every observed change is therefore listed as unmentioned.")
        R.table(["#", "Claim", "Source", "Status", "Evidence"],
                [[x["id"], x["text"], x["source"], badge(STATUS_COLOUR[x["status"]], x["status"]), x["evidence"]] for x in claims_eval])

    # 4) behavior changes
    R.h(2, "What changed in behavior", "changes")
    if not groups and not imp:
        R.p("No behavior change: no test went from passing to failing, and every test module still loads.")
    if imp:
        R.h(3, f"Import failure: {len(imp['modules'])} test module(s) cannot load")
        R.table(["Item", "Value"], [
            ["Error", tidy(imp["signature"])],
            ["Before (old)", f"package import: {', '.join(f'{k}: {v}' for k, v in (get(rec, 'dependent_import', 'old') or {}).items()) or NA}"],
            ["After (new)", "; ".join(f"{k}: {v}" for k, v in imp["package_errors"].items()) or NA],
            ["Tests that passed before and can no longer run", str(len(imp["lost"]))],
            ["Affected modules (first 8)", ", ".join(imp["modules"][:8]) + (f", and {len(imp['modules']) - 8} more" if len(imp["modules"]) > 8 else "")],
            ["Full lists", f"{rel('class-import_failure.txt')}, {rel('class-lost_tests.txt')}"],
        ])
    if groups:
        R.p(f"{sum(len(g['tests']) for _, g in groups)} real break(s) in {len(groups)} group(s), largest first.")
        R.table(["#", "Error after the change", "Tests"], [[str(i), tidy(s), str(len(g["tests"]))] for i, (s, g) in enumerate(groups, 1)])
        for i, (s, g) in enumerate(groups, 1):
            ex = g["example"]
            R.h(3, f"Group {i}: {len(g['tests'])} test(s)")
            R.p(f"**Error:** {tidy(s)}")
            names = [t.split("::", 1)[-1] for t in g["tests"]]
            R.p("**Affected tests:** " + ", ".join(f"`{n}`" for n in names[:6]) + (f", and {len(names) - 6} more" if len(names) > 6 else "")
                + f" (full list: {rel('class-real_break.txt')})")
            R.p(f"**Example:** `{ex['test']}`. Before: {', '.join(ex['old'])} (old runs). After: {', '.join(ex['new'])} (new runs).")
            out = e_lines(ex["text"]) or [first_line(ex["message"])]
            R.code("Before (old side): test passed, no error output\n\nAfter (new side):\n" + "\n".join(out))

    # 5) what went right
    R.h(2, "What went right", "right")
    gates = rec.get("gates") or {}
    right = []
    labels = {"versions_verified": "Correct versions installed", "env_identical_except_upstream": "Only the upstream version differs between sides",
              "venv_isolated": "Isolated environments", "threads_pinned": "Thread count pinned to 1", "runs_complete": "All runs completed",
              "old_side_healthy": "Old side healthy (baseline is trustworthy)", "stability": "Repeatable results",
              "no_secrets_in_logs": "No secrets in logs", "schema_valid": "Record format valid"}
    for k, g in gates.items():
        if g.get("pass"):
            right.append([badge("green", "pass"), labels.get(k, k), g.get("detail", NA)])
    if rec.get("runs_per_side"):
        right.append([badge("green", "pass") if rec["runs_per_side"] >= 3 else badge("red", "fail"), "Runs per side", f"{rec['runs_per_side']} (minimum 3), alternating old and new"])
    if "no network" in str(rec.get("network", "")):
        right.append([badge("green", "pass"), "Guardrails respected", "tests ran with no network; nothing was posted or filed by the runner"])
    if rec.get("matches_expected") == "yes":
        right.append([badge("green", "pass"), "Matches the prediction written before the run", fmt(rec.get("expected"))])
    R.table(["Status", "Check", "Detail"], right or [[badge("grey", NA), NA, NA]])

    # 6) what went wrong
    R.h(2, "What went wrong and how to fix it", "wrong")
    pr_issues, env_issues = [], []
    if imp:
        pr_issues.append([f"{dep} cannot be imported on the new side ({tidy(imp['signature'])})",
                          f"The change removed or renamed something {dep} uses. Either keep a deprecated alias in {up} for one release, or {dep} must release a fix before this ships."])
    for i, (s, g) in enumerate(groups or [], 1):
        pr_issues.append([f"Group {i}: {len(g['tests'])} test(s) fail with: {tidy(s)}",
                          f"Decide whether this change is intended. If yes, document it as a breaking change and tell {dep}; if not, fix it in the PR. Reproduce with the command below and the example test."])
    for x in claims_eval:
        if x["status"] == "false":
            pr_issues.append([f"Claim {x['id']} is contradicted: {x['text']}", "Correct the PR description or fix the code so the claim holds."])
    fixes = DEFAULT_FIXES
    try:
        sys.path.insert(0, os.path.join(root, "harness"))
        from brlib import FIXES as fixes  # noqa
    except Exception:
        pass
    for k in d["req_fail"] + d["adv_fail"]:
        env_issues.append([f"Check failed: {labels.get(k, k)} ({get(gates, k, 'detail') or NA})", fixes.get(k, "not available")])
    if ab:
        sig = "; ".join(f"{s} ({n})" for s, n in (rec.get("top_error_signatures_already_broken") or [])[:3]) or NA
        env_issues.append([f"{ab} test(s) of {dep} already fail before the change: {sig}",
                           f"Not caused by this change; ignore for this decision. To clean up the baseline, pin the tool versions {dep} expects or deselect these tests (record it in subset_note)."])
    if fl:
        env_issues.append([f"{fl} flaky test(s)", fixes.get("stability", NA)])
    if "no network" not in str(rec.get("network", "")):
        env_issues.append(["Tests were not network-isolated", "Run on a machine where 'unshare -rn true' works, without --no-net-isolation."])
    if rec.get("pin_overridden"):
        env_issues.append([f"{dep}'s declared upper bound on {up} was overridden", f"Results show what would happen if {dep} allowed {up} {nv}; mention this when reporting."])
    if rec.get("subset_note"):
        env_issues.append([f"Only a subset of tests ran: {rec['subset_note']}", "Run the full suite before relying on a VERIFIED verdict."])
    if rec.get("matches_expected") == "no":
        env_issues.append([f"Result differs from the prediction written before the run ({rec.get('expected')})", "Check whether the prediction or the run is wrong; hand-check one example."])
    R.h(3, "Issues in the PR or release")
    R.table(["Issue", "How to fix"], pr_issues) if pr_issues else R.p("None found.")
    R.h(3, "Issues in our test environment")
    R.table(["Issue", "How to fix"], env_issues) if env_issues else R.p("None found.")

    # 7) trust checks
    R.h(2, "Trust checks", "trust")
    st = rec.get("stability") or {}
    tot = st.get("tests")
    mt = rec.get("machine_type") or {}
    te = rec.get("thread_env") or {}
    req = [k for k, g in gates.items() if g.get("required", True)]
    trust = [
        ["Required checks (gates)", badge("green" if not d["req_fail"] else "red", f"{len(req) - len(d['req_fail'])} of {len(req)} passed"), ", ".join(d["req_fail"]) or "all passed"],
        ["Advisory checks", badge("green" if not d["adv_fail"] else "amber", f"{len([k for k in gates if k not in req]) - len(d['adv_fail'])} of {len([k for k in gates if k not in req])} passed"), ", ".join(d["adv_fail"]) or "all passed"],
        ["Golden cases (known answers)", badge("green" if golden and all(g["ok"] for g in golden) else ("grey" if not golden else "red"),
                                               f"{sum(1 for g in golden if g['ok'])} of {len(golden)} hold" if golden else NA),
         "checked against the stored golden records (harness " + ", ".join(sorted({str(g['harness']) for g in golden})) + "), not re-run for this report"
         + (". This run is itself one of the golden cases, so this check is partly circular for it" if any(g["run"] == rec["id"] for g in golden) else "") if golden else NA],
        ["Flaky rate", badge("green" if (fl == 0 and tot) else ("grey" if not tot else "amber"), f"{fl} of {tot} ({fl / tot:.1%})" if tot else NA), f"stability old {fmt(st.get('old_stable_rate'))}, new {fmt(st.get('new_stable_rate'))}"],
        ["Network during tests", badge("green" if "no network" in str(rec.get("network", "")) else "red", "off" if "no network" in str(rec.get("network", "")) else "on or unknown"), fmt(rec.get("network"))],
        ["Threads", badge("green" if te and all(v == "1" for v in te.values()) else "amber", "pinned to 1" if te and all(v == "1" for v in te.values()) else (NA if not te else "not all 1")), ", ".join(f"{k}={v}" for k, v in te.items()) or NA],
        ["Machine", badge("blue", fmt(mt.get("label") or rec.get("machine"))), f"{fmt(mt.get('cpu_model'))}, {fmt(mt.get('cpu_count'))} CPUs, {fmt(mt.get('ram_gb'))} GB RAM, {fmt(mt.get('os'))} {fmt(mt.get('arch'))}, CI: {fmt(mt.get('ci'))}"],
        ["Report matches the record", *consistency(rec, groups, imp)],
        ["Prediction before the run", badge("green" if rec.get("matches_expected") == "yes" else ("red" if rec.get("matches_expected") == "no" else "grey"), fmt(rec.get("matches_expected"))), fmt(rec.get("expected"))],
    ]
    R.table(["Check", "Status", "Detail"], trust)
    if golden:
        R.table(["Golden case", "Status", "Detail"], [[g["case"], badge("green" if g["ok"] else ("grey" if g["ok"] is None else "red"), "holds" if g["ok"] else ("not available" if g["ok"] is None else "fails")), g["detail"]] for g in golden])

    # 8) checklist
    R.h(2, "Reviewer checklist", "checklist")
    R.checklist([
        "I read the verdict and the recommended action.",
        "I checked the claims vs reality table for any 'false' or 'unmentioned change' rows.",
        "I looked at the largest behavior-change group and its example error." if (groups or imp) else "I confirmed there are no behavior changes.",
        "I confirmed the required checks passed (Trust checks).",
        "I am satisfied the environment issues (if any) do not change the decision.",
    ])
    R.p("**Decision:** ☐ Approve ☐ Approve with notes ☐ Reject ☐ Re-run    Reviewer: ________  Date: ________", "decision")

    # 9) reproduce
    R.h(2, "Reproduce this run", "repro")
    cmd = repro_command(args, rec)
    R.code(cmd) if cmd else R.p("Command: not available (args.json missing).")
    R.p("Needs Linux x86_64, uv 0.12 or newer, git and unshare. The command makes fresh environments and does not post anything.")

    # 10) appendix
    R.h(2, "Appendix", "appendix")
    R.h(3, "Commits and versions")
    R.table(["Item", "Value"], [
        ["PR", f"{pr.get('repo')}#{pr.get('number')} ({pr.get('url')})" if pr else NA],
        ["PR merge commit / base commit", f"{fmt(pr.get('merge_commit'))} / {fmt(pr.get('base_commit'))}" if pr else NA],
        ["Upstream", f"{up}: old {ov}, new {nv} (requested {fmt(rec.get('new_version_requested'))})"],
        ["Upstream source", fmt(rec.get("new_direct_url")) if rec.get("new_direct_url") else "PyPI release wheels (no commit recorded)"],
        ["Dependent", f"{dep} {dv}"],
        ["Tests from", f"{fmt(rec.get('test_source'))}; selection: {fmt(rec.get('test_selection'))}"],
        ["Python", fmt(rec.get("python"))],
        ["Environment difference", ", ".join(rec.get("env_diff") or []) or NA],
        ["Runner", f"harness {fmt(rec.get('harness_version'))}, {fmt(rec.get('workers'))} workers, import mode {fmt(rec.get('import_mode'))}, per-test timeout {fmt(rec.get('test_timeout_s'))} s, memory cap {fmt(rec.get('mem_cap_gb'))} GB"],
        ["Record schema", f"v{fmt(rec.get('schema_version'))}, sha256 {str(rec.get('schema_sha256') or NA)[:16]}..."],
        ["Run by", f"{fmt(rec.get('who'))} on {fmt(rec.get('machine'))}, {fmt(rec.get('date_ist'))}"],
        ["Hand check", fmt(rec.get("hand_check"))],
        ["Upstream issue", fmt(rec.get("upstream_issue"))],
        ["AI explanation", fmt(get(rec, "explanation", "status"))],
    ])
    R.h(3, "Timings")
    du = rec.get("duration_s") or {}
    R.p(f"Total wall time {fmt(du.get('total_wall'))} s; mean test time old {fmt(du.get('tests_old_mean'))} s, new {fmt(du.get('tests_new_mean'))} s.")
    R.table(["Side", "Run", "Exit", "Seconds", "pytest summary"],
            [[p["side"], str(p["run"]), str(p.get("exit")), str(p.get("seconds", NA)), p.get("pytest_summary") or NA] for p in rec.get("per_run", [])])
    R.h(3, "Artifacts")
    arts = []
    for pat, what in [("record.json", "Full record"), ("args.json", "Run arguments"), ("setup.log", "Setup log"),
                      ("freeze-old.txt", "Installed packages, old"), ("freeze-new.txt", "Installed packages, new"),
                      ("freeze-diff.txt", "Package difference"), ("pytest-*.log", "pytest logs"), ("junit-*.xml", "JUnit XML"),
                      ("class-*.txt", "Test lists per class")]:
        fs = sorted(glob.glob(os.path.join(rd, pat)))
        arts.append([what, ", ".join(rel(os.path.basename(f)) for f in fs) if fs else NA])
    R.table(["What", "Path (relative to this report)"], arts)

    R.h(2, "Glossary", "glossary")
    R.table(["Term", "Meaning"], [[a, b] for a, b in GLOSSARY])
    summary = dict(id=rec["id"], subject=subject, dependent=f"{dep} {dv}", verdict=d["verdict"], action=d["action"],
                   confidence=d["confidence"], colour=d["colour"], why=d["why"], date=rec.get("date_ist"),
                   real_break=rb, import_failure=ib, flaky=fl)
    return R, summary


# ---------------------------------------------------------------- renderers

def md_cell(v):
    if isinstance(v, tuple) and v[0] == "badge":
        return f"{EMOJI.get(v[1], '')} **{v[2]}**"
    return str(v).replace("|", "\\|").replace("\n", " ")


def to_md(R):
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
            out.append("| " + " | ".join(b[1]) + " |\n|" + "---|" * len(b[1]) + "\n" +
                       "\n".join("| " + " | ".join(md_cell(c) for c in r) + " |" for r in b[2]) + "\n")
        elif k == "banner":
            _, v, a, c, why, col, scope = b
            out.append(f"> ## {EMOJI[col]} {v}\n>\n> **Recommended action:** {a}  \n> **Confidence:** {c}. {why}\n"
                       + (f">\n> {scope}\n" if scope else ""))
    return "\n".join(out)


def inline(s):
    s = html.escape(str(s))
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
table{border-collapse:collapse;width:100%;margin:8px 0 12px;font-size:12.5px}th,td{border:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top;overflow-wrap:break-word}
th{background:#f6f8fa}tr:nth-child(even) td{background:#fbfbfc}
code{font:12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#f3f4f6;padding:1px 4px;border-radius:3px}
pre{font:11.5px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#f6f8fa;border:1px solid var(--line);padding:10px;border-radius:6px;white-space:pre-wrap;word-break:break-all}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-weight:600;font-size:11.5px;white-space:nowrap}
.b-green{color:var(--green);background:var(--green-bg)}.b-amber{color:var(--amber);background:var(--amber-bg)}
.b-red{color:var(--red);background:var(--red-bg)}.b-grey{color:var(--grey);background:var(--grey-bg)}.b-blue{color:var(--blue);background:var(--blue-bg)}
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
@media print{body{margin:0;max-width:none;padding:0}h2{break-after:avoid}pre,.banner{break-inside:avoid}tr{break-inside:avoid}thead{display:table-header-group}}
"""


def html_cell(v):
    if isinstance(v, tuple) and v[0] == "badge":
        return f'<span class="badge b-{v[1]}">{html.escape(v[2])}</span>'
    parts = str(v).split(", ")
    if parts and all(re.fullmatch(r"(\.\./)+[\w./*-]+", x) for x in parts):
        return ", ".join(f"<a href='{html.escape(x)}'>{html.escape(x.rsplit('/', 1)[-1])}</a>" for x in parts)
    return inline(v)


def to_html(R, title):
    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>{CSS}</style></head><body>"]
    action_col = {"Approve": "green", "Approve with notes": "green", "Reject": "red", "Re-run": "grey"}
    for b in R.blocks:
        k = b[0]
        if k == "h":
            out.append(f"<h{b[1]}{' id=' + chr(34) + b[3] + chr(34) if b[3] else ''}>{inline(b[2])}</h{b[1]}>")
        elif k == "p":
            out.append(f"<p{' class=' + chr(34) + b[2] + chr(34) if b[2] else ''}>{inline(b[1])}</p>")
        elif k == "ul":
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in b[1]) + "</ul>")
        elif k == "check":
            out.append("<ul class='check'>" + "".join(f"<li>{inline(x)}</li>" for x in b[1]) + "</ul>")
        elif k == "code":
            out.append(f"<pre>{html.escape(b[1])}</pre>")
        elif k == "table":
            out.append("<table><thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in b[1]) + "</tr></thead><tbody>" +
                       "".join("<tr>" + "".join(f"<td>{html_cell(c)}</td>" for c in r) + "</tr>" for r in b[2]) + "</tbody></table>")
        elif k == "banner":
            _, v, a, c, why, col, scope = b
            out.append(f"<div class='banner {col}'><div class='v'>{html.escape(v)}</div>"
                       f"<div class='row'>Recommended action: <span class='action badge b-{action_col.get(a, 'grey')}'>{html.escape(a)}</span>"
                       f" &nbsp; Confidence: <strong>{html.escape(c)}</strong></div>"
                       f"<div class='row'>{inline(why)}</div>"
                       + (f"<div class='scope'>{inline(scope)}</div>" if scope else "") + "</div>")
    out.append("</body></html>")
    return "\n".join(out)


def to_pdf(html_path, pdf_path):
    chrome = next((shutil.which(x) for x in ("google-chrome", "chromium", "chromium-browser") if shutil.which(x)), None)
    if not chrome:
        return "no chrome/chromium on PATH; PDF not generated"
    with tempfile.TemporaryDirectory() as prof:
        r = subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", f"--user-data-dir={prof}",
                            "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", "file://" + os.path.abspath(html_path)],
                           capture_output=True, text=True, timeout=120)
    return None if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0 else f"chrome failed: {r.stderr[-300:]}"


# ---------------------------------------------------------------- batch summary

ORDER = {("NEEDS ATTENTION", "Reject"): 0, ("NEEDS ATTENTION", "Approve with notes"): 1, ("COULD NOT VERIFY", "Re-run"): 2,
         ("VERIFIED", "Approve with notes"): 3, ("VERIFIED", "Approve"): 4}


def write_summary(summaries, out_dir, title, formats):
    s = sorted(summaries, key=lambda x: (ORDER.get((x["verdict"], x["action"]), 9), x["id"]))
    R = Report()
    R.h(1, title)
    n = lambda v: sum(1 for x in s if x["verdict"] == v)
    R.p(f"Generated {datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')}. {len(s)} report(s): "
        f"{n('NEEDS ATTENTION')} need attention, {n('COULD NOT VERIFY')} could not be verified, {n('VERIFIED')} verified. "
        "Items that need a decision are listed first.", "meta")
    R.table(["Verdict", "Action", "Confidence", "Subject", "Tested against", "Why", "Report"],
            [[badge(x["colour"], x["verdict"]), badge({"Reject": "red", "Re-run": "grey"}.get(x["action"], "green"), x["action"]),
              x["confidence"], x["subject"], x["dependent"], x["why"], f"{x['id']}/REPORT.html"] for x in s])
    R.h(2, "Verdict meanings")
    R.table(["Verdict", "Meaning"], [[badge("amber", "NEEDS ATTENTION"), "The run is trustworthy and found a problem: breaks, import failures, or a false claim."],
                                      [badge("grey", "COULD NOT VERIFY"), "The run failed its own trust checks. No conclusion; re-run after fixing."],
                                      [badge("green", "VERIFIED"), "The run is trustworthy and found no behavior change."]])
    os.makedirs(out_dir, exist_ok=True)
    if "md" in formats:
        open(os.path.join(out_dir, "SUMMARY.md"), "w").write(to_md(R).replace("/REPORT.html", "/REPORT.md"))
    hp = os.path.join(out_dir, "SUMMARY.html")
    h = to_html(R, title)
    h = re.sub(r"<td>([\w.-]+)/REPORT\.html</td>", lambda m: f"<td><a href='{m.group(1)}/REPORT.html'>open report</a> (<a href='{m.group(1)}/REPORT.pdf'>PDF</a>)</td>", h)
    open(hp, "w").write(h)
    if "pdf" in formats:
        return to_pdf(hp, os.path.join(out_dir, "SUMMARY.pdf"))


# ---------------------------------------------------------------- main

def render_one(record, root, out_dir, claims=None, golden_dir=None, obs=None, formats=("md", "html", "pdf")):
    rec, rd, cl, args, junit, golden = load_inputs(record, root, claims, golden_dir, obs)
    os.makedirs(out_dir, exist_ok=True)
    R, summary = build(rec, rd, cl, args, junit, golden, out_dir, root)
    title = f"Reviewer report {rec['id']}"
    if "md" in formats:
        open(os.path.join(out_dir, "REPORT.md"), "w").write(to_md(R))
    hp = os.path.join(out_dir, "REPORT.html")
    open(hp, "w").write(to_html(R, title))
    err = to_pdf(hp, os.path.join(out_dir, "REPORT.pdf")) if "pdf" in formats else None
    summary["pdf_error"] = err
    return summary


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root_default = os.path.dirname(os.path.dirname(here))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("records", nargs="+", help="record.json paths")
    ap.add_argument("--root", default=root_default, help="research root (record 'logs' paths are relative to it)")
    ap.add_argument("--out", required=True, help="output dir; one subdir per run id plus SUMMARY.*")
    ap.add_argument("--claims-dir", default=None, help="dir with <run id>.claims.json files (optional)")
    ap.add_argument("--golden-dir", default=None, help="default: <root>/evals/golden")
    ap.add_argument("--observations", default=None, help="default: <root>/research/observations.jsonl")
    ap.add_argument("--summary-title", default="Proof-of-Change reviewer summary")
    ap.add_argument("--formats", default="md,html,pdf")
    a = ap.parse_args()
    formats = a.formats.split(",")
    gd = a.golden_dir or os.path.join(a.root, "evals", "golden")
    ob = a.observations or os.path.join(a.root, "research", "observations.jsonl")
    sums = []
    for r in a.records:
        rid = json.load(open(r))["id"]
        cp = os.path.join(a.claims_dir, f"{rid}.claims.json") if a.claims_dir else None
        s = render_one(r, a.root, os.path.join(a.out, rid), cp, gd, ob, formats)
        sums.append(s)
        print(f"{rid}: {s['verdict']} | {s['action']} | confidence {s['confidence']}" + (f" | PDF: {s['pdf_error']}" if s["pdf_error"] else ""))
    err = write_summary(sums, a.out, a.summary_title, formats)
    print("summary:", os.path.join(a.out, "SUMMARY.html"), err or "")


if __name__ == "__main__":
    main()
