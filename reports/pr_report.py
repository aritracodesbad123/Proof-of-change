"""Reviewer reports for Proof-of-Change PR runs (records written by ops/daily_run.py).

    python -m reports.pr_report ops/runs/2026-10-10 --out reports/daily/2026-10-10
    python -m reports.pr_report decide reports/daily/2026-10-10/pandas-70520 approve --by Aritra --note "ok"

One run folder in, one REPORT.md/.html/.pdf per PR plus SUMMARY.md/.html/.pdf (needs-attention first) out. Same
sections, renderers and verdict vocabulary as reports/reviewer.py (docs/REPORT_SPEC.md), adapted to a main-vs-PR
test run: there is no dependent library here, the PR's own tests are run on main and on the PR, 3 times per side.
Every claim and every observed change cites a real line of a pytest log, and the citations are re-read and verified.
Standard library only. Never contacts anything: it reads the run folder and writes files.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

from reports import reviewer as rv
from reports.reviewer import Report, badge, link

VERDICT = {"verified": ("VERIFIED", "green"), "needs_attention": ("NEEDS ATTENTION", "amber"),
           "could_not_verify": ("COULD NOT VERIFY", "grey")}
CATEGORIES = [  # comparison key, plain-English label, how bad
    ("regressions", "pass on main but fail on the PR", "bad"),
    ("new_tests_failing", "are new in the PR and fail", "bad"),
    ("removed_tests", "ran on main but are missing on the PR side", "check"),
    ("other_changes", "changed result in another way (for example passed -> skipped)", "check"),
    ("flaky", "gave different results between the 3 runs of the same side (flaky)", "note"),
    ("fixed", "fail on main and pass on the PR", "good"),
]
SUMMARY_RE = re.compile(r"\b\d+ (passed|failed|errors?|skipped)\b.* in [0-9.]+s")
DECISIONS = {"approve": "Approve", "approve_with_notes": "Approve with notes", "reject": "Reject", "re_run": "Re-run"}


def run_id(rec: dict) -> str:
    return rec.get("_dir") or f"{rec.get('library', 'pr')}-{rec['pr']}"


# ---------------------------------------------------------------- log citations
class Logs:
    """pytest-<side>-<n>.log files of one PR folder; finds the exact line that backs a statement."""

    def __init__(self, prdir: Path):
        self.dir = prdir
        self._cache: dict[str, list[str]] = {}

    def lines(self, name: str) -> list[str]:
        if name not in self._cache:
            p = self.dir / name
            self._cache[name] = p.read_text(errors="replace").splitlines() if p.exists() else []
        return self._cache[name]

    def cite(self, name: str, i: int) -> dict:
        return {"file": name, "line": i + 1, "quote": self.lines(name)[i].strip()[:160]}

    def summary(self, side: str, run: int = 1) -> dict | None:
        name = f"pytest-{side}-{run}.log"
        ls = self.lines(name)
        for i in range(len(ls) - 1, -1, -1):
            if SUMMARY_RE.search(ls[i]):
                return self.cite(name, i)
        return None

    def test_line(self, test_id: str, side: str = "pr") -> dict | None:
        """The FAILED/ERROR line pytest -rfE printed for this test, in the first run log that has one."""
        name = test_id.split("::")[-1]
        for run in (1, 2, 3):
            fn = f"pytest-{side}-{run}.log"
            for i, ln in enumerate(self.lines(fn)):
                if ln.startswith(("FAILED", "ERROR")) and name in ln:
                    return self.cite(fn, i)
        return None


def verify(cits: list[dict | None], prdir: Path) -> tuple[str, str]:
    """Re-open every cited file and check the quoted text is on that line."""
    real = [c for c in cits if c]
    if not real:
        return "SKIP", "no log lines to cite (no tests ran)"
    bad = []
    for c in real:
        p = prdir / c["file"]
        ls = p.read_text(errors="replace").splitlines() if p.exists() else []
        if not (0 < c["line"] <= len(ls) and c["quote"] in ls[c["line"] - 1]):
            bad.append(f"{c['file']}:{c['line']}")
    missing = len(cits) - len(real)
    if bad:
        return "FAIL", f"{len(bad)} citation(s) do not match their log line: {', '.join(bad[:3])}"
    if missing:
        return "WARN", f"{len(real)} citation(s) verified; {missing} statement(s) have no matching log line"
    return "PASS", f"{len(real)} citation(s), every one re-read from its log file and matched"


def cite_text(c: dict | None, rel) -> str:
    if not c:
        return "no matching log line"
    return link(f"{c['file']}:{c['line']}", rel(c["file"])) + f" «{c['quote']}»"


# ---------------------------------------------------------------- checks and verdict
def checks(rec: dict) -> list[list]:
    """Nathan's evals and guardrails for one PR run: [name, status, detail, how to fix]."""
    out = []
    pr = rec.get("per_run") or []
    n = rec.get("runs_per_side", 3)
    if pr:
        sides = {s: sum(1 for x in pr if x["side"] == s and x.get("exit") not in ("no-targets", "timeout")) for s in ("main", "pr")}
        ok = sides["main"] == sides["pr"] == n == 3
        out.append(["3 alternating runs per side", "PASS" if ok else "FAIL", f"main {sides['main']}, PR {sides['pr']} of {n}",
                    "" if ok else "Re-run with the default --runs 3 and look for timeouts in the pytest logs."])
    elif rec.get("verdict") != "could_not_verify":
        out.append(["3 alternating runs per side", "FAIL", "no test runs recorded", "Re-run; see setup logs."])
    te = rec.get("thread_env") or {}
    ok = bool(te) and all(v == "1" for v in te.values())
    out.append(["Single-thread environment", "PASS" if ok else "FAIL", ", ".join(f"{k}={v}" for k, v in te.items()) or "not recorded",
                "" if ok else "Run through ops/daily_run.py, which pins all thread counts to 1."])
    mt = rec.get("machine_type") or {}
    out.append(["Machine type recorded", "PASS" if mt else "FAIL",
                f"{mt.get('label', '?')} {mt.get('arch', '')} {mt.get('cpu_count', '')} cpus".strip() if mt else "missing",
                "" if mt else "Re-run with the current ops/daily_run.py."])
    posted = rec.get("posted_upstream")
    out.append(["Nothing posted upstream", "PASS" if posted is False else "FAIL",
                "GitHub was only read" if posted is False else f"posted_upstream={posted!r}",
                "" if posted is False else "Stop and investigate: the run must never post."])
    flaky = (rec.get("comparison") or {}).get("flaky") or []
    if flaky:
        out.append(["No flaky tests", "WARN", f"{len(flaky)} test(s) changed result between runs of the same side",
                    "Read them under 'What changed'; a flaky test is not evidence either way."])
    cur, head = rec.get("current_head_sha"), rec.get("head_sha")
    if cur and head and cur != head:
        out.append(["PR unchanged since tested", "WARN", f"tested {head[:12]}, PR now at {cur[:12]}",
                    "Run the check again to test the PR's latest commit."])
    rr = rv.replay_row(rv.latest_replay())
    out.append([rr[0], {"all passed": "PASS", "FAILED": "FAIL"}.get(rr[1][2], "SKIP"), rr[2],
                "Run the known-answer tests again (Validation Center, button 2) and fix what fails." if rr[1][2] == "FAILED" else ""])
    pc = (rec.get("main_side") or {}).get("pip_check")
    if pc and pc != "ok":
        out.append(["Main-side packages consistent (pip check)", "WARN", str(pc)[:120], "Usually harmless; see setup-main.log."])
    return out


def decide(rec: dict, chk: list[list]) -> dict:
    v = rec.get("verdict", "could_not_verify")
    bad_replay = rv.replay_failure(None, rv.latest_replay())
    if bad_replay:  # Jonathan's rule: a failed known-answer replay means no report is trusted
        return dict(verdict="COULD NOT VERIFY", colour="grey", action="Re-run", confidence="Low",
                    conf_why="The known-answer tests failed in the latest replay.", why=bad_replay)
    fails = [c for c in chk if c[1] == "FAIL"]
    warns = [c for c in chk if c[1] == "WARN"]
    if v == "could_not_verify" or fails:
        why = rec.get("reason") if v == "could_not_verify" else "the run failed its own checks: " + "; ".join(c[0] for c in fails)
        return dict(verdict="COULD NOT VERIFY", colour="grey", action="Re-run", confidence="Low",
                    conf_why="The run did not finish cleanly, so it says nothing about the PR.", why=why)
    verdict, colour = VERDICT[v]
    conf = "Medium" if warns else "High"
    conf_why = (("Some checks gave warnings: " + "; ".join(c[0] for c in warns)) if warns
                else "Every check passed and every claim cites a log line.")
    if v == "needs_attention":
        return dict(verdict=verdict, colour=colour, action="Reject", confidence=conf, conf_why=conf_why,
                    why=rec.get("reason", ""))
    c = rec.get("comparison") or {}
    notes = warns or c.get("fixed")
    return dict(verdict=verdict, colour=colour, action="Approve with notes" if notes else "Approve", confidence=conf,
                conf_why=conf_why, why=rec.get("reason", ""))


# ---------------------------------------------------------------- claims
def claims(rec: dict, logs: Logs) -> list[dict]:
    """Rows of the claims table. Nemotron claim extraction is not built yet, so the PR's own words (its title) are
    shown as 'not testable', and the implicit claim every PR makes, 'existing tests still pass', is checked."""
    c = rec.get("comparison") or {}
    summ = logs.summary("pr", 1)
    rows = [dict(id="C1", text=rec.get("title", "?"), source="PR title", status="not testable",
                 evidence="reading claims out of the PR description is not built yet (needs Nemotron); the tests below check behavior",
                 citation=summ)]
    if c:
        broke = (c.get("regressions") or []) + (c.get("new_tests_failing") or [])
        rows.append(dict(id="C2", text="Existing behavior is kept: tests that pass on main still pass", source="implied by every PR",
                         status="false" if broke else "proven",
                         evidence=(f"{len(broke)} test(s) fail on the PR, e.g. {broke[0]}" if broke else
                                   f"no test that passes on main fails on the PR ({c.get('same', 0)} unchanged, 3 runs per side)"),
                         citation=logs.test_line(broke[0]) if broke else summ))
    for key, label, kind in CATEGORIES:
        items = c.get(key) or []
        if not items or key == "fixed":
            continue
        first = items[0].split(": ")[0]
        cit = logs.test_line(first) if kind == "bad" else (logs.summary("main", 1) if key == "removed_tests" else summ)
        rows.append(dict(id="-", text="Change not in the PR description", source="this run", status="unmentioned change",
                         evidence=f"{len(items)} test(s) {label}, e.g. {items[0]}", citation=cit))
    return rows


# ---------------------------------------------------------------- build
def build(rec: dict, prdir: Path, out_dir: Path, decision: dict | None = None) -> tuple[Report, dict]:
    logs = Logs(prdir)
    c = rec.get("comparison") or {}
    chk = checks(rec)
    rows = claims(rec, logs) if rec.get("per_run") else []
    cstat, cdetail = verify([r["citation"] for r in rows], prdir)
    chk.append(["Every claim cites a real log line", cstat, cdetail,
                "" if cstat in ("PASS", "SKIP") else "Regenerate the report; if it persists, the logs were edited or truncated."])
    d = decide(rec, chk)
    pr_ref = f"{rec['repo']}#{rec['pr']}"
    subject = f"{pr_ref}: {rec.get('title', '')}"

    def rel(name: str) -> str:
        return os.path.relpath(prdir / name, out_dir)

    R = Report()
    R.h(1, f"Reviewer report: {subject}")
    R.p(f"Run `{run_id(rec)}`, tested {rec.get('tested_at_ist', '?')} by ops/daily_run.py (route {rec.get('route', '-')}). "
        f"Report generated {datetime.datetime.now(rv.IST).strftime('%Y-%m-%d %H:%M IST')} by reports/pr_report.py.", "meta")
    reason = {"VERIFIED": "The PR's tests behave the same or better than on main, in all 3 runs per side.",
              "NEEDS ATTENTION": "The run is trustworthy and found a difference a person should look at.",
              "COULD NOT VERIFY": "The run did not produce a usable comparison, so there is no conclusion about the PR."}[d["verdict"]]
    R.banner(d["verdict"], d["action"], d["confidence"], reason + " " + d["conf_why"], d["colour"],
             "Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.")

    R.h(2, "Summary in plain English", "summary")
    todo = {"Approve": "Nothing to fix. You can approve.",
            "Approve with notes": "You can approve; read the notes under 'What went wrong' first.",
            "Reject": "Do not approve as is. Read 'What changed in behavior' and decide with the PR author.",
            "Re-run": "Do not decide yet. Fix the problem under 'How to fix' and run the check again."}[d["action"]]
    R.bullets([f"**What it says it does:** {rec.get('title', '?')} ({link(pr_ref, rec.get('url', ''))}).",
               f"**What we observed:** {d['why']}.",
               f"**What you should do:** {todo}"])

    R.h(2, "Claims vs reality", "claims")
    if rows:
        R.table(["#", "Claim (source)", "Status", "What we observed", "Log line"],
                [[r["id"], f"{r['text']} ({r['source']})", badge(rv.STATUS_COLOUR[r["status"]], r["status"]), r["evidence"],
                  cite_text(r["citation"], rel)] for r in rows])
        R.p(f"Citation check ({cstat}): {cdetail}.", "meta")
    else:
        R.p("No tests ran, so no claim could be checked.")

    R.h(2, "What changed in behavior", "changes")
    if c:
        R.table(["What", "Count", "Examples"],
                [["Tests unchanged", str(c.get("same", 0)), "-"], ["New tests that pass", str(c.get("new_tests_passing", 0)), "-"]]
                + [[f"Tests that {label}", str(len(c.get(k) or [])), ", ".join(f"`{t}`" for t in (c.get(k) or [])[:5]) or "-"]
                   for k, label, _ in CATEGORIES])
        for t, m in list((c.get("messages") or {}).items())[:3]:
            R.p(f"`{t}` fails with: `{str(m).splitlines()[0][:200] if m else ''}`")
    else:
        R.p(f"Not measured: {rec.get('reason', 'no comparison')}.")

    R.h(2, "What went right", "right")
    right = [f"Tested `{rec.get('head_sha', '?')[:12]}` of the PR against main ({rec.get('route', '-')} route)."]
    right += [f"{x[0]}: {x[2]}." for x in chk if x[1] == "PASS"]
    R.bullets(right)

    R.h(2, "What went wrong and how to fix it", "wrong")
    wrong = [[x[0], badge("red" if x[1] == "FAIL" else "amber", x[1]), x[2], x[3]] for x in chk if x[1] in ("FAIL", "WARN")]
    if rec.get("verdict") == "could_not_verify":
        wrong.insert(0, ["Run did not finish", badge("grey", "COULD NOT VERIFY"), rec.get("reason", ""),
                         "Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly."])
    if d["verdict"] == "NEEDS ATTENTION":
        wrong.append(["Behavior difference found", badge("amber", "finding"), rec.get("reason", ""),
                      "This is about the PR, not the run: read the failing tests and their log lines, then decide."])
    if wrong:
        R.table(["Issue", "Status", "Detail", "How to fix"], wrong)
    else:
        R.p("Nothing went wrong.")

    R.h(2, "Evals and guardrails (Nathan)", "evals")
    R.table(["Check", "Result", "Detail"],
            [[x[0], badge({"PASS": "green", "FAIL": "red", "WARN": "amber"}.get(x[1], "grey"), x[1]), x[2]] for x in chk])

    R.h(2, "Checklist", "checklist")
    R.checklist(["I read the verdict and the plain-English summary.",
                 "Every 'false' or 'unmentioned change' row has a log line I can open.",
                 "Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).",
                 "I recorded my decision (see below)."])
    if decision:
        R.p(f"**Decision recorded:** {DECISIONS.get(decision['decision'], decision['decision'])} by {decision.get('by', '?')} "
            f"on {decision.get('date', '?')}" + (f". Note: {decision['note']}" if decision.get("note") else "."))
    else:
        R.p(f"**Decision recorded:** none yet. To record one, run `make decide REPORT={out_dir} DECISION=approve` "
            "(or `reject`, `approve_with_notes`, `re_run`).")

    R.h(2, "Rerun command", "rerun")
    R.code(f"make check PR={rec.get('url', '<PR URL>')}")

    R.h(2, "Evidence links", "evidence")
    ev = [link(f"Pull request {pr_ref}", rec.get("url", ""))]
    for name in ["record.json", "pr.diff", "setup-main.log", "setup-pr.log", "build-pr.log", "patch.log", "git.log"] + \
            [f"pytest-{s}-{i}.log" for i in (1, 2, 3) for s in ("main", "pr")] + [f"junit-{s}-1.xml" for s in ("main", "pr")]:
        if (prdir / name).exists():
            ev.append(link(name, rel(name)))
    for side in ("main", "pr"):
        s = logs.summary(side, 1)
        if s:
            ev.append(f"{side} run 1 result: " + cite_text(s, rel))
    R.bullets(ev)

    R.h(2, "Glossary", "glossary")
    R.table(["Term", "Meaning"], [
        ["main", "The library as it is today, without the PR."],
        ["PR", "Pull request: a proposed change to the library."],
        ["run", "One full pass of the selected tests. We do 3 per side, alternating main and PR."],
        ["flaky", "A test that gives different results when nothing changed; it is ignored as evidence."],
        ["log line", "A line in a pytest-*.log file: the raw output the verdict is based on."],
        ["route", "How the two sides were built: nightly+patch, source-build or source-pair (see docs/OPERATIONS.md)."]])

    summary = dict(id=run_id(rec), subject=subject, dependent="its own tests", verdict=d["verdict"], action=d["action"],
                   confidence=d["confidence"], colour=d["colour"], why=d["why"] or "-",
                   evals="APPROVE" if not [x for x in chk if x[1] == "FAIL"] else "REJECT", claims=[r["status"] for r in rows],
                   citations=cstat)
    return R, summary


def render_run(run_dir: str | Path, out: str | Path, formats=("md", "html", "pdf"), title: str | None = None) -> list[dict]:
    """Render every PR in an ops/daily_run.py run folder. Returns the summary rows."""
    run_dir, out = Path(run_dir).resolve(), Path(out).resolve()
    recs = []
    for p in sorted(run_dir.glob("*/record.json")):
        rec = json.loads(p.read_text())
        rec.setdefault("_dir", p.parent.name)
        recs.append((rec, p.parent))
    if not recs:
        raise SystemExit(f"no */record.json under {run_dir}: is this an ops/runs/<date> folder?")
    if "pdf" in formats and not rv.find_chrome():
        print("note: no Chrome/Chromium found, so no PDFs; HTML and Markdown are written", file=sys.stderr)
        formats = tuple(f for f in formats if f != "pdf")
    rows = []
    for rec, prdir in recs:
        od = out / run_id(rec)
        od.mkdir(parents=True, exist_ok=True)
        dec_p = od / "DECISION.json"
        R, s = build(rec, prdir, od, json.loads(dec_p.read_text()) if dec_p.exists() else None)
        (od / "SOURCE.json").write_text(json.dumps({"run_dir": str(run_dir), "out": str(out), "formats": list(formats)}))
        if "md" in formats:
            (od / "REPORT.md").write_text(rv.to_md(R))
        (od / "REPORT.html").write_text(rv.to_html(R, f"Reviewer report {run_id(rec)}"))
        if "pdf" in formats:
            s["pdf_error"] = rv.to_pdf(str(od / "REPORT.html"), str(od / "REPORT.pdf"))
        rows.append(s)
        print(f"{s['id']}: {s['verdict']} | {s['action']} | confidence {s['confidence']} | citations {s['citations']}")
    rv.write_summary(rows, str(out), title or f"Proof-of-Change daily summary: {run_dir.name}", formats)
    print(f"summary: {out / 'SUMMARY.html'}")
    return rows


def record_decision(report_dir: str | Path, decision: str, by: str, note: str = "") -> Path:
    od = Path(report_dir).resolve()
    if decision not in DECISIONS:
        raise SystemExit(f"DECISION must be one of: {', '.join(DECISIONS)}")
    src = od / "SOURCE.json"
    if not src.exists():
        raise SystemExit(f"{od} is not a report folder (no SOURCE.json). Use the folder that contains REPORT.html.")
    (od / "DECISION.json").write_text(json.dumps({"decision": decision, "by": by, "note": note,
                                                  "date": datetime.datetime.now(rv.IST).strftime("%Y-%m-%d %H:%M IST")}))
    s = json.loads(src.read_text())
    render_run(s["run_dir"], s["out"], tuple(s["formats"]))
    return od / "REPORT.html"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["decide"]:
        ap = argparse.ArgumentParser(prog="python -m reports.pr_report decide")
        ap.add_argument("report_dir")
        ap.add_argument("decision", choices=sorted(DECISIONS))
        ap.add_argument("--by", default=os.environ.get("USER", "reviewer"))
        ap.add_argument("--note", default="")
        a = ap.parse_args(argv[1:])
        print(f"decision recorded: {record_decision(a.report_dir, a.decision, a.by, a.note)}")
        return 0
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", help="an ops/runs/<date> folder written by ops/daily_run.py")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--formats", default="md,html,pdf")
    ap.add_argument("--title", default=None)
    a = ap.parse_args(argv)
    render_run(a.run_dir, a.out, tuple(a.formats.split(",")), a.title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
