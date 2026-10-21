"""Reviewer reports for Proof-of-Change PR runs (records written by ops/daily_run.py).

    python -m reports.pr_report ops/runs/2026-10-10 --out reports/daily/2026-10-10
    python -m reports.pr_report decide reports/daily/2026-10-10/pandas-70520 approve --by reviewer --note "ok"

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

from poc import coverage_gate, demo_helper
from reports import reviewer as rv
from reports.reviewer import Report, badge, link

VERDICT = {"verified": ("VERIFIED", "green"), "needs_attention": ("NEEDS ATTENTION", "amber"),
           "could_not_verify": ("COULD NOT VERIFY", "grey"), "no_code_change": ("NO CODE CHANGE", "grey")}
CATEGORIES = [  # comparison key, plain-English label, how bad
    ("regressions", "pass on main but fail on the PR", "bad"),
    ("new_tests_failing", "are new in the PR and fail", "bad"),
    ("removed_tests", "ran on main but are missing on the PR side", "check"),
    ("other_changes", "changed result in another way (for example passed -> skipped)", "check"),
    ("flaky", "gave different results between the 3 runs of the same side (flaky)", "note"),
    ("fixed", "fail on main and pass on the PR", "good"),
    ("skipped_missing_dependency", "are new or changed but did not run because an optional module is missing",
     "check"),
    ("reparametrized", "were re-parametrized (same test, new parameter ids; not counted as removed)", "note"),
    ("load_failed_pr", "fail to load on the PR side only (their tests no longer run)", "check"),
    ("load_failed_main", "fail to load on main only (no baseline for their tests)", "check"),
    ("load_failed_both", "fail to load on both sides (their tests did not run)", "note"),
    ("preexisting_failures", "fail identically on both sides (already broken on main)", "note"),
]
SUMMARY_RE = re.compile(r"\b\d+ (passed|failed|errors?|skipped)\b.* in [0-9.]+s")
DECISIONS = {"approve": "Approve", "approve_with_notes": "Approve with notes", "reject": "Reject", "re_run": "Re-run"}


def run_id(rec: dict) -> str:
    return rec.get("_dir") or f"{rec.get('library', 'pr')}-{rec['pr']}"


def _ai_probe_downgraded(rec: dict) -> bool:
    """True when the stored record was already lowered because no AI-written probe ran a changed line.

    Re-applying the coverage gate restores the verdict from before that gate, which would hide this downgrade.
    The AI-probe gate is applied again only in that case, so a record that was not downgraded stays as it was."""
    before = rec.get("verdict_before_ai_probe_gate")
    if before and before != rec.get("verdict"):
        return True
    reason = rec.get("reason") or ""
    return rec.get("verdict") == "could_not_verify" and "no AI-written probe" in reason


def normalize(rec: dict, dirname: str | None = None) -> dict:
    """Flat view of a record. pr_run records (schema rev 3+, ops/daily_run.py) keep the PR in a `pr` object and the
    durations in a `duration_s` object; older synthetic records were flat. The coverage gate is applied here too
    (idempotent), so reports rebuilt from records written before the gate existed follow the same rules.
    A record the AI-probe gate already downgraded keeps that lower verdict (display only; this does not re-judge)."""
    r = dict(rec)
    p = rec.get("pr")
    if isinstance(p, dict):
        r.update(repo=p.get("repo", rec.get("repo")), pr=p.get("number"), title=p.get("title", rec.get("title", "")),
                 url=p.get("url", rec.get("url", "")), head_sha=p.get("head_sha", rec.get("head_sha")),
                 merge_commit=p.get("merge_commit"))
        r.setdefault("current_head_sha", rec.get("current_head_sha"))
    logs = (rec.get("logs") or "").strip("/")
    r.setdefault("_dir", dirname or logs or None)
    if not r["_dir"]:
        r.pop("_dir")
    downgraded = _ai_probe_downgraded(r)
    out = coverage_gate.apply(r)
    if downgraded:
        from ops.daily_run import ai_probe_gate
        out = ai_probe_gate(out)
    return out


def side_of(x: dict) -> str:
    """per_run side: pr_run records use the schema's old/new, older records main/pr."""
    return {"old": "main", "new": "pr"}.get(x.get("side"), x.get("side"))


def noun(key: str) -> str:
    return "test module(s)" if key.startswith("load_failed") else "test(s)"


def item_str(x) -> str:
    """A comparison entry as text: plain test ids, or dicts (re-parametrized / skipped-for-dependency entries)."""
    if isinstance(x, dict):
        if "tests_affected" in x:
            return f"{x['module']} ({x['tests_affected']} test(s) on the other side)"
        if "removed_ids" in x:
            return f"{x['test']} ({len(x['removed_ids'])} -> {len(x['added_ids'])} ids)"
        return f"{x.get('test', '?')} (needs {x['module']})" if x.get("module") else str(x.get("test", x))
    return str(x)


def dependency_gaps(rec: dict, prdir: Path) -> tuple[dict, dict]:
    """({module: n} new/changed tests skipped for a missing optional module,
        {module: n} unchanged tests skipped on both sides for the same reason)."""
    c = rec.get("comparison") or {}
    changed: dict = {}
    for d in c.get("skipped_missing_dependency") or []:
        changed[d.get("module", "?")] = changed.get(d.get("module", "?"), 0) + 1
    try:
        from ops.daily_run import unchanged_dependency_skips
        unchanged = unchanged_dependency_skips(prdir, c)
    except Exception:  # noqa: BLE001  (the runner is optional for rendering)
        unchanged = {}
    return changed, unchanged


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
    """Evals and guardrails for one PR run: [name, status, detail, how to fix]."""
    out = []
    pr = rec.get("per_run") or []
    n = rec.get("runs_per_side", 3)
    if pr:
        sides = {s: sum(1 for x in pr if side_of(x) == s and x.get("exit") not in ("no-targets", "timeout"))
                 for s in ("main", "pr")}
        ok = sides["main"] == sides["pr"] == n == 3
        out.append(["3 alternating runs per side", "PASS" if ok else "FAIL", f"main {sides['main']}, PR {sides['pr']} of {n}",
                    "" if ok else "Re-run with the default --runs 3 and look for timeouts in the pytest logs."])
    elif rec.get("verdict") not in ("could_not_verify", "no_code_change"):
        out.append(["3 alternating runs per side", "FAIL", "no test runs recorded", "Re-run; see setup logs."])
    ec = rec.get("exit_check")
    if ec:
        out.append(["pytest exit codes explained", "PASS" if ec.get("explained") else "FAIL", ec.get("detail", ""),
                    "" if ec.get("explained") else "Read the pytest logs: " + "; ".join(ec.get("problems", [])[:2])])
    g = rec.get("coverage_gate") or {}
    if g:
        note = g.get("note") or "-"
        if g.get("changed") and "compiled" in (g.get("kind") or ""):
            st, fix = "WARN", "Ask for (or add) a test that calls the changed compiled module, or review it by hand."
        elif g.get("changed"):
            st, fix = "WARN", "Widen the test mapping, or ask the author for a test that runs the changed lines."
        elif "predates the coverage gate" in note:
            st, fix = "WARN", ("Not a measurement: this record is older than the coverage gate. Re-run the PR with the "
                               "current ops/daily_run.py to measure it.")
        elif g.get("confidence") == "lower" and "NOT MEASURED" in note.upper():
            st, fix = "WARN", "The coverage run did not produce data (see coverage.why); run the check again."
        elif g.get("confidence") == "lower":
            st, fix = "WARN", "Under half of the changed lines ran: ask for a test that covers the rest."
        else:
            st, fix = "PASS", ""
        out.append(["Changed code was exercised (coverage gate)", st, note, fix])
    changed, unchanged = dependency_gaps(rec, Path(rec.get("_prdir", ".")))
    if changed or unchanged:
        out.append(["Optional modules installed", "WARN",
                    "; ".join(x for x in [
                        ("new/changed tests blocked: " + ", ".join(f"{m} ({n})" for m, n in changed.items())) if changed else "",
                        ("unchanged tests skipped on both sides: " + ", ".join(f"{m} ({n})" for m, n in unchanged.items()))
                        if unchanged else ""] if x),
                    "Add the module(s) to optional_test_deps for this library in ops/daily_run.py and run again."])
    p = rec.get("probes")
    if p:
        its = p.get("items") or []
        bad = [f"{it['id']} {x['side']}#{x['run']}" for it in its for x in it.get("per_run", []) if not x.get("ok", True)]
        if p.get("refused"):
            out.append(["Probes passed the freeze rule", "WARN",
                        "; ".join(f"{x['path']}: {x['why']}" for x in p["refused"][:3]),
                        "A probe changed or appeared after PR-side execution started, so it was not run; re-run the check."])
        if p.get("status") == "none":
            out.append(["Probes ran on both sides", "SKIP", "no probe for this PR", ""])
        elif p.get("status") == "error" or bad:
            out.append(["Probes ran on both sides", "WARN", "; ".join(p.get("errors", []) + bad[:3]) or "probe error",
                        "Read the probe-*.log files; a probe that cannot run is not evidence either way."])
        else:
            out.append(["Probes ran on both sides", "PASS", f"{len(its)} probe(s), "
                        f"{its[0].get('runs_per_side', 3)} alternating runs per side, every run printed its observations", ""])
    te = rec.get("thread_env") or {}
    # Thread-count variables must be 1. PYTHONHASHSEED is recorded in the same block (fixed hash seed) and must be 0;
    # it is not a thread count, so it is checked against its own value.
    threads = {k: v for k, v in te.items() if k != "PYTHONHASHSEED"}
    ok = bool(threads) and all(v == "1" for v in threads.values()) and te.get("PYTHONHASHSEED", "0") == "0"
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
        shown = ", ".join(f"`{t}`" for t in flaky[:5])
        more = f" (+{len(flaky) - 5})" if len(flaky) > 5 else ""
        out.append(["No flaky tests", "WARN",
                    f"{len(flaky)} test(s) changed result between runs of the same side: {shown}{more}",
                    "Listed for the record. A flaky test is not a regression and is not evidence either way."])
    cmp = rec.get("comparison") or {}
    pr_only = list(cmp.get("pr_unstable") or [])
    pr_noisy = [t for t in (cmp.get("pr_unstable_noisy") or []) if t not in pr_only]
    unstable = pr_only + pr_noisy
    if unstable:
        shown = ", ".join(f"`{t}`" for t in unstable[:5])
        more = f" (+{len(unstable) - 5})" if len(unstable) > 5 else ""
        if pr_only:
            level = "FAIL"
            fix = "A test that passes on every base run and fails on some pull-request runs is a possible regression."
        else:
            level = "WARN"
            fix = "Every pull-request run differed, so this is too mixed to call a regression. It is not verified."
        out.append(["Tests unstable only on the pull request", level,
                    f"{len(unstable)} test(s) stable on the base and unstable only on the pull request: {shown}{more}",
                    fix])
    cur, head = rec.get("current_head_sha"), rec.get("head_sha")
    if cur and head and cur != head:
        out.append(["PR unchanged since tested", "WARN", f"tested {head[:12]}, PR now at {cur[:12]}",
                    "Run the check again to test the PR's latest commit."])
    rr = rv.replay_row(rv.latest_replay())
    out.append([rr[0], {"all passed": "PASS", "FAILED": "FAIL"}.get(rr[1][2], "SKIP"), rr[2],
                "Run the known-answer tests again and fix what fails." if rr[1][2] == "FAILED" else ""])
    pc = (rec.get("main_side") or {}).get("pip_check")
    if pc and pc != "ok":
        out.append(["Main-side packages consistent (pip check)", "WARN", str(pc)[:120], "Usually harmless; see setup-main.log."])
    return out


def decide(rec: dict, chk: list[list]) -> dict:
    v = rec.get("verdict", "could_not_verify")
    bad_replay = rv.replay_failure(None, rv.latest_replay())
    if bad_replay:  # rule: a failed known-answer replay means no report is trusted
        return dict(verdict="COULD NOT VERIFY", colour="grey", action="Re-run", confidence="Low",
                    conf_why="The known-answer tests failed in the latest replay.", why=bad_replay)
    if v == "no_code_change":
        return dict(verdict="NO CODE CHANGE", colour="grey", action="Approve with notes", confidence="High",
                    conf_why="Every changed file is a type stub or a py.typed marker, so behaviour was not checked.",
                    why=rec.get("reason", ""))
    infra = rec.get("infrastructure_failure")
    if isinstance(infra, dict) and infra.get("kind") == "oom":
        return dict(verdict="COULD NOT VERIFY", colour="grey", action="Re-run", confidence="Low",
                    conf_why="The compiler ran out of memory. That is an infrastructure failure, not a finding "
                             "about the pull request.",
                    why=rec.get("reason", ""))
    fails = [c for c in chk if c[1] == "FAIL"]
    warns = [c for c in chk if c[1] == "WARN"]
    g = rec.get("coverage_gate") or {}
    if v == "could_not_verify" and g.get("changed") and not fails:
        return dict(verdict="COULD NOT VERIFY", colour="grey", action="Review by hand", confidence="Low",
                    conf_why="The tests ran cleanly but did not exercise the changed code, so they say little about "
                             "this change.", why=rec.get("reason", ""), gate=True)
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
                 evidence=("claims are read out of the PR description only by model-written probes (--model-provider, "
                           "see Probes); the tests below check behavior"),
                 citation=summ)]
    if c:
        broke = (c.get("regressions") or []) + (c.get("new_tests_failing") or [])
        rows.append(dict(id="C2", text="Existing behavior is kept: tests that pass on main still pass",
                         source="implied by every PR",
                         status="false" if broke else "proven",
                         evidence=(f"{len(broke)} test(s) fail on the PR, e.g. {broke[0]}" if broke else
                                   f"no test that passes on main fails on the PR ({c.get('same', 0)} unchanged, 3 runs per side)"),
                         citation=logs.test_line(broke[0]) if broke else summ))
    prows = probe_claim_rows(rec)
    if any(r["id"].startswith("P-") for r in prows):
        rows = rows[1:]   # the PR's claims are checked by the probe rows; drop the 'title: not testable' placeholder
    rows += prows
    for key, label, kind in CATEGORIES:
        items = c.get(key) or []
        if not items or key == "fixed":
            continue
        if kind == "note":
            continue  # re-parametrized / pre-existing: shown under 'What changed', not a change the PR introduced
        first = item_str(items[0]).split(": ")[0].split(" (")[0]
        cit = logs.test_line(first) if kind == "bad" else (logs.summary("main", 1) if key == "removed_tests" else summ)
        rows.append(dict(id="-", text="Change not in the PR description", source="this run", status="unmentioned change",
                         evidence=f"{len(items)} {noun(key)} {label}, e.g. {item_str(items[0])}", citation=cit))
    return rows


# ---------------------------------------------------------------- probes
PROBE_STATUS = {"proven": "proven", "false_claim": "false", "needs_human": "not observed", "flaky": "flaky",
                "unstable_on_pr": "unstable on the pull request",
                "unmentioned": "unmentioned change", "not_testable": "not testable", "no_difference": "proven"}
PROBE_RESULT = {"proven": ("green", "as claimed"), "no_difference": ("green", "same on both sides"),
                "false_claim": ("red", "contradicts the claim"), "unmentioned": ("amber", "differs, not in the PR description"),
                "needs_human": ("amber", "no change although the claim says it changes"),
                "flaky": ("amber", "flaky between runs"),
                "unstable_on_pr": ("amber", "unstable only on the pull request"),
                "not_testable": ("grey", "probe could not run")}
LABEL_RANK = ["false_claim", "flaky", "unstable_on_pr", "needs_human", "not_testable", "proven", "no_difference"]


def probe_items(rec: dict) -> list[dict]:
    return (rec.get("probes") or {}).get("items") or []


def deciding_ids(rec: dict) -> set:
    """Ids of the probes that could decide the verdict under the record's baseline (ops/daily_run.probe_items)."""
    from ops.daily_run import probe_items as deciding
    return {it["id"] for it in (deciding(rec.get("probes"), rec.get("baseline")) or {}).get("items") or []}


def generator_label(it: dict) -> str:
    g = (it.get("freeze") or {}).get("generator") or it.get("generator") or {}
    if g.get("label"):
        return g["label"]
    return "fixed probe (no generator recorded; treated as post-hoc)" if it.get("source", "library") == "library" \
        else f"{it.get('source')} probe"


def num(v):
    return round(v, 6) if isinstance(v, float) else [num(x) for x in v] if isinstance(v, list) else (
        {k: num(x) for k, x in v.items()} if isinstance(v, dict) else v)


def short(v, n: int = 90) -> str:
    t = json.dumps(num(v), sort_keys=True)
    return t if len(t) <= n else t[:n - 3] + "..."


def observed(o: dict) -> str:
    """What the probe saw, in one line: the field-level differences, or the shared value."""
    if o["state"] == "same":
        return f"same on both sides: `{short(o['main'])}`"
    ds = o.get("diffs") or []
    return "; ".join(f"`{d['field'] or 'value'}`: {short(d.get('main'), 40)} -> {short(d.get('pr'), 40)}" for d in ds[:4]) + (
        f" (+{len(ds) - 4} more)" if len(ds) > 4 else "")


def probe_claim_rows(rec: dict) -> list[dict]:
    """Claims-table rows from the probes: one per claim a probe checks, and one per difference no claim covers."""
    rows = []
    decide_ids = deciding_ids(rec)
    for it in probe_items(rec):
        if it["id"] not in decide_ids:
            continue   # informational under this baseline (e.g. differential probes under full)
        for cl in it.get("claims", []):
            obs = [o for o in it["observations"] if o.get("claim") == cl["id"]]
            if not obs:
                rows.append(dict(id=f"P-{cl['id']}", text=cl["text"], source=cl.get("source", "probe"), status="not testable",
                                 evidence=f"probe {it['id']} has no observation for this claim", citation=None))
                continue
            worst = min(obs, key=lambda o: LABEL_RANK.index(o["label"]) if o["label"] in LABEL_RANK else 0)
            rows.append(dict(id=f"P-{cl['id']}", text=cl["text"], source=cl.get("source", "probe"),
                             status=PROBE_STATUS[worst["label"]],
                             evidence=f"probe {it['id']}, {worst['name']}: {observed(worst)}",
                             citation=(worst.get("citations") or {}).get("pr")))
        for o in it["observations"]:
            if o["label"] == "unmentioned":
                rows.append(dict(id="-", text="Change not in the PR description", source=f"probe {it['id']}",
                                 status="unmentioned change", evidence=f"{o['name']}: {observed(o)}",
                                 citation=(o.get("citations") or {}).get("pr")))
    return rows


def uncovered_diff_differences(rec: dict) -> list[dict]:
    """Differential-probe observations that no claim covers. Display only: nothing here changes a verdict."""
    rows = []
    for it in probe_items(rec):
        if it.get("source") != "diff":
            continue
        for o in it.get("observations") or []:
            state = o.get("state")
            if o.get("label") == "unmentioned" or (not o.get("claim") and state not in ("same", "flaky")):
                rows.append({"probe": it.get("id") or "?", "name": o.get("name") or "?", "observation": o})
    return rows


def uncovered_diff_section(R, rec: dict) -> None:
    rows = uncovered_diff_differences(rec)
    if not rows:
        return
    R.h(2, "Differences no claim covers", "uncovered-diff")
    R.p("These differences come from differential probes. No claim in the pull request covers them. "
        "The list is for reading the report. It does not change the verdict.")
    R.table(["Probe", "Observation", "What the probe saw (main -> PR)"],
            [[r["probe"], f"`{r['name']}`", observed(r["observation"])] for r in rows])


def probes_section(R, rec: dict, rel) -> list[dict]:
    """The 'Probes' section. Returns the citations shown (for the citation check)."""
    p = rec.get("probes")
    R.h(2, "Probes", "probes")
    mp = rec.get("model_provider") or {}
    if mp.get("note"):
        R.p(f"Model-written probes: {mp['note']}.", "meta")
    if not p:
        R.p("No probes ran: " + (f"baseline {rec['baseline']} uses none." if rec.get("baseline") == "tests"
                                 else "this record predates probes."))
        return []
    items = probe_items(rec)
    for x in p.get("refused") or []:
        R.p(f"**Refused ({x.get('source', 'probe')}): `{x['path']}`**: {x['why']}. It was not run on the PR side.")
    if not items:
        R.p("No probe ran for this PR (no fixed probe in probes/<owner>/<repo>/<pr>.py and no model-written or "
            "differential probe), so only the tests were compared."
            + (" Probe errors: " + "; ".join(p.get("errors", [])) if p.get("errors") else ""))
        return []
    R.p("A probe is a small deterministic script run on both sides in the same environments as the tests, "
        f"{items[0].get('runs_per_side', 3)} alternating runs per side. It prints JSON observations; plain code "
        "(poc/diff.py) compares them. A difference that no claim of the PR covers needs attention. Every probe was "
        "frozen (content sha256) before any PR-side code ran, and checked against that freeze before each PR-side run. "
        "Only a live model probe is blind; fixed probes and recorded model fixtures are known-answer cases.", "meta")
    cits = []
    decide_ids = deciding_ids(rec)
    for it in items:
        fz = it.get("freeze") or {}
        role = "" if it["id"] in decide_ids else f"; informational under baseline {rec.get('baseline') or 'full'}"
        R.p(f"**{it['id']}** ({generator_label(it)}{role}"
            + (f", `{it['path']}`" if it.get("path") else "")
            + (f", frozen `{fz['sha256'][:12]}` at {fz.get('frozen_at', '?')}" if fz.get("sha256") else "")
            + f"): {it.get('about', '')}")
        if it.get("claims"):
            R.bullets([f"P-{c['id']} ({c.get('source', 'claim')}): {c['text']} Expects the covered observations to "
                       f"{'differ' if c['expect'] == 'differs' else 'stay the same'}." for c in it["claims"]])
        rows = []
        for o in it["observations"]:
            colour, txt = PROBE_RESULT.get(o["label"], ("grey", o["label"]))
            cm, cp = (o.get("citations") or {}).get("main"), (o.get("citations") or {}).get("pr")
            cits += [cm, cp]
            rows.append([f"`{o['name']}`", f"P-{o['claim']}" if o.get("claim") else "-", badge(colour, txt), observed(o),
                         cite_text(cm, rel) + "<br>" + cite_text(cp, rel)])
        R.table(["Observation", "Claim", "Result", "What the probe saw (main -> PR)", "Log lines (main, PR)"], rows)
    return cits


# ---------------------------------------------------------------- build
def build(rec: dict, prdir: Path, out_dir: Path, decision: dict | None = None) -> tuple[Report, dict]:
    rec = normalize(rec, prdir.name) | {"_prdir": str(prdir)}
    logs = Logs(prdir)
    c = rec.get("comparison") or {}
    chk = checks(rec)
    rows = claims(rec, logs) if rec.get("per_run") else []
    cstat, cdetail = verify([r["citation"] for r in rows], prdir)
    chk.append(["Every claim cites a real log line", cstat, cdetail,
                "" if cstat in ("PASS", "SKIP") else "Regenerate the report; if it persists, the logs were edited or truncated."])
    probe_cits = [c for it in probe_items(rec) for o in it["observations"] for c in (o.get("citations") or {}).values()]
    pstat, pdetail = verify(probe_cits, prdir) if probe_cits else ("SKIP", "")
    if probe_cits:
        chk.append(["Every probe observation cites its output line", pstat, pdetail,
                    "" if pstat in ("PASS", "SKIP") else "Regenerate the report; the probe outputs were edited or are missing."])
    d = decide(rec, chk)
    pr_ref = f"{rec['repo']}#{rec['pr']}"
    subject = f"{pr_ref}: {rec.get('title', '')}"

    def rel(name: str) -> str:
        return os.path.relpath(prdir / name, out_dir)

    R = Report()
    R.h(1, f"Reviewer report: {subject}")
    commit = rec.get("poc_commit")
    commit_bit = f" Proof-of-Change commit `{commit}`." if commit else ""
    R.p(f"Run `{run_id(rec)}`, tested {rec.get('tested_at_ist', '?')} by ops/daily_run.py (route {rec.get('route', '-')})."
        f"{commit_bit} "
        f"Report generated {datetime.datetime.now(rv.IST).strftime('%Y-%m-%d %H:%M IST')} by reports/pr_report.py.", "meta")
    from ops.daily_run import BASELINE_TEXT
    bl = rec.get("baseline") or "full"
    R.p(f"Baseline: **{bl}** ({BASELINE_TEXT.get(bl, bl)})" + ("" if rec.get("baseline") else
                                                               ", recorded before baselines existed") + ".", "meta")
    reason = {"VERIFIED": "The PR's tests behave the same or better than on main, in all 3 runs per side.",
              "NEEDS ATTENTION": "The run is trustworthy and found a difference a person should look at.",
              "COULD NOT VERIFY": "The run did not produce a usable comparison, so there is no conclusion about the PR."}[d["verdict"]]
    if d.get("gate"):
        reason = "Not fully verified: the tests ran cleanly, but the changed code never ran under them."
    R.banner(d["verdict"], d["action"], d["confidence"], reason + " " + d["conf_why"], d["colour"],
             "Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.")

    R.h(2, "Summary in plain English", "summary")
    todo = {"Approve": "Nothing to fix. You can approve.",
            "Approve with notes": "You can approve; read the notes under 'What went wrong' first.",
            "Reject": "Do not approve as is. Read 'What changed in behavior' and decide with the PR author.",
            "Re-run": "Do not decide yet. Fix the problem under 'How to fix' and run the check again.",
            "Review by hand": "The tests did not exercise this change. Read the diff yourself, or ask the author for "
                              "a test that runs the changed code; re-running will not change this."}[d["action"]]
    R.bullets([f"**What it says it does:** {rec.get('title', '?')} ({link(pr_ref, rec.get('url', ''))}).",
               f"**What we observed:** {d['why']}.",
               f"**What you should do:** {todo}"])
    expl = rec.get("explanation") or {}
    if expl.get("status") == "wired" and expl.get("text"):
        R.p(str(expl["text"]))
        if expl.get("quotes"):
            R.p("Quoted from the record: " + "; ".join(f"`{q}`" for q in expl["quotes"][:5]), "meta")
        R.p("Model summary is advisory; the code verdict above is authoritative.", "meta")
    agents = rec.get("agents") or {}
    roles = agents.get("roles") if isinstance(agents, dict) else None
    if roles:
        R.h(3, "Agent swarm (advisory)")
        rows_a = []
        for role in roles:
            note = role.get("note") or ""
            if role.get("labels"):
                note = f"{len(role['labels'])} labels" + (f"; {note}" if note else "")
            if role.get("notes"):
                note = "; ".join(str(n) for n in role["notes"][:3]) + (f"; {note}" if note else "")
            rows_a.append([role.get("role", "?"), role.get("model") or "-", role.get("status") or "-", note or "-"])
        R.table(["Role", "Model", "Status", "Notes"], rows_a)
        R.p(agents.get("note") or "judge/helper/summary are advisory; code owns the verdict", "meta")
    helper = rec.get("demo_helper") if isinstance(rec.get("demo_helper"), dict) else None
    helper_notes = (helper or {}).get("notes") if isinstance(helper, dict) else None
    if helper_notes:
        R.h(3, "Demo helper")
        R.p("These notes are background from the console and the daily check. They do not change the verdict.")
        R.p(demo_helper.RETRY_LIMITS)
        R.bullets([str(note) for note in helper_notes])
    from poc import related_reports
    background = rec.get("related_reports") if isinstance(rec.get("related_reports"), dict) else None
    background_text = str((background or {}).get("text") or "").strip()
    if background_text:
        R.h(3, related_reports.REPORT_LABEL)
        R.p(background_text)

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
                ([["Tests that actually ran (main / PR, fewest of the runs)",
                   f"{c['executed'].get('main', '?')} / {c['executed'].get('pr', '?')}", "-"]] if c.get("executed") else [])
                + [["Tests unchanged", str(c.get("same", 0)), "-"], ["New tests that pass", str(c.get("new_tests_passing", 0)), "-"]]
                + [[f"{'Test modules' if k.startswith('load_failed') else 'Tests'} that {label}", str(len(c.get(k) or [])),
                    ", ".join(f"`{item_str(t)}`" for t in (c.get(k) or [])[:5]) or "-"]
                   for k, label, _ in CATEGORIES])
        for t, m in list((c.get("messages") or {}).items())[:3]:
            R.p(f"`{t}` fails with: `{str(m).splitlines()[0][:200] if m else ''}`")
    else:
        R.p(f"Not measured: {rec.get('reason', 'no comparison')}.")

    if probes_section(R, rec, rel):
        R.p(f"Citation check ({pstat}): {pdetail}.", "meta")
    uncovered_diff_section(R, rec)

    R.h(2, "Was the changed code exercised?", "coverage")
    g, cov = rec.get("coverage_gate") or {}, rec.get("coverage") or {}
    m = g.get("measurement") or coverage_gate.measurement(rec, bool((rec.get("files") or {}).get("package_py")))
    R.p({"measured": f"**Coverage: MEASURED** by coverage.py on the PR side ({cov.get('seconds', '?')} s run).",
         "not measured: predates gate": "**Coverage: NOT MEASURED, record predates the coverage gate.** No coverage "
                                        "run exists for this record; nothing below is a measurement.",
         "not measured": f"**Coverage: NOT MEASURED** ({cov.get('why') or cov.get('status') or 'no data'}).",
         "not needed": "**Coverage: not needed** (no changed Python lines)."}.get(m, f"Coverage: {m}."))
    R.p(f"Coverage gate ({g.get('kind', '-')}, confidence {g.get('confidence', '-')}): {g.get('note') or '-'}."
        + (f" This changed the verdict from {rec.get('verdict_before_coverage_gate')} to {rec.get('verdict')}."
           if g.get("changed") else ""))
    if cov.get("status") == "measured" and cov.get("files"):
        R.table(["Changed file", "Changed executable lines", "Of those, ran"],
                [[f"`{f['file']}`", "-" if f.get("changed_lines_total") is None else str(f["changed_lines_total"]),
                  f.get("note") or str(f.get("changed_lines_covered"))] for f in cov["files"]])
    R.p("How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come "
        "from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such "
        "a change only counts as verified when the PR adds or changes a test for that module.", "meta")
    changed, unchanged = dependency_gaps(rec, prdir)
    if changed or unchanged:
        R.h(2, "Missing optional modules", "optional")
        R.bullets(([f"{n} new/changed test(s) did not run because `{m}` is not installed: the change was not exercised "
                    "(could not verify)." for m, n in changed.items()]) +
                  [f"{n} unchanged test(s) skipped on both sides because `{m}` is not installed (coverage gap, verdict "
                   "unaffected)." for m, n in sorted(unchanged.items(), key=lambda kv: -kv[1])])

    R.h(2, "What went right", "right")
    right = [f"Tested `{(rec.get('head_sha') or '?')[:12]}` of the PR against main ({rec.get('route', '-')} route)."]
    right += [f"{x[0]}: {x[2]}." for x in chk if x[1] == "PASS"]
    R.bullets(right)

    R.h(2, "What went wrong and how to fix it", "wrong")
    wrong = [[x[0], badge("red" if x[1] == "FAIL" else "amber", x[1]), x[2], x[3]] for x in chk if x[1] in ("FAIL", "WARN")]
    if d.get("gate"):
        wrong.insert(0, ["Changed code not exercised", badge("grey", "NOT FULLY VERIFIED"), rec.get("reason", ""),
                         "Read the diff by hand, or ask for a test that runs the changed code."])
    elif rec.get("verdict") == "could_not_verify":
        wrong.insert(0, ["Run did not finish", badge("grey", "COULD NOT VERIFY"), rec.get("reason", ""),
                         "Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly."])
    if d["verdict"] == "NEEDS ATTENTION":
        wrong.append(["Behavior difference found", badge("amber", "finding"), rec.get("reason", ""),
                      "This is about the PR, not the run: read the failing tests and their log lines"
                      + (" and the Probes section" if (rec.get("probes") or {}).get("summary", {}).get("flagged") else "")
                      + ", then decide."])
    if wrong:
        R.table(["Issue", "Status", "Detail", "How to fix"], wrong)
    else:
        R.p("Nothing went wrong.")

    R.h(2, "Evals and guardrails", "evals")
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
            [f"pytest-{s}-{i}.log" for i in (1, 2, 3) for s in ("main", "pr")] + [f"junit-{s}-1.xml" for s in ("main", "pr")] + \
            ["coverage-pytest.log", "coverage-pr.json"] + \
            [f for it in probe_items(rec) for side in ("main", "pr") for f in (it.get("outputs") or {}).get(side, [])[:1]]:
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
        ["route", "How the two sides were built: nightly+patch, source-build or source-pair (see docs/OPERATIONS.md)."],
        ["changed lines covered", "How many of the PR's changed, executable Python lines ran during the PR side's tests."],
        ["re-parametrized", "A test whose parameter ids changed (renamed cases); the new ids are judged on their own."]])

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
        recs.append((normalize(json.loads(p.read_text()), p.parent.name), p.parent))
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
    gated = [(r, s) for (r, _), s in zip(recs, rows) if (r.get("coverage_gate") or {}).get("changed")]

    def extra(R):
        if gated:
            R.h(2, "Changed by the coverage gate")
            R.bullets([f"{s['subject']}: {r.get('verdict_before_coverage_gate')} -> {r['verdict']} "
                       f"({(r.get('coverage_gate') or {}).get('note')})" for r, s in gated])
        hist = run_history(run_dir)
        if hist:
            R.h(2, "Re-runs")
            R.p("Earlier attempts of this run date are kept under superseded/attempt-N/. The day's PR selection is "
                "frozen: the final attempt re-tests every PR that any earlier attempt selected.")
            R.bullets([f"{h['attempt']}: {(h['note'].splitlines() or [''])[0].lstrip('# ')}. Selected "
                       f"{len(h['selected'])} PR(s), {len(h['verdicts'])} record(s)." for h in hist])

    rv.write_summary(rows, str(out), title or f"Proof-of-Change daily summary: {run_dir.name}", formats, extra)
    print(f"summary: {out / 'SUMMARY.html'}")
    return rows


def run_history(run_dir: Path) -> list[dict]:
    try:
        from ops.daily_run import attempt_history
        return attempt_history(run_dir)
    except Exception:  # noqa: BLE001
        return []


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
