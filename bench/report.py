"""Judge-readable evidence report for one benchmark results folder.

    python -m bench.report bench/results/<date> [--out DIR]

Reads only the files bench/run.py writes: run_meta.json, one JSON result per case and arm, and the
check record under ops/<arm>/runs/bench-<case id>/*/record.json when that file is there. Counts and
the probe-uplift table come from bench.summarize, unchanged. Writes evidence.md and evidence.html.
The decision line repeats each deciding arm's recorded verdict. It does not restate, raise, or lower it.
Missing fields are the words "not recorded". The whole output passes bench.run.redact_all before it is written.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

from bench.manifest import VERDICTS
from bench.run import PROBE_RUNS, RED_LABELS, arm_dir_name, find_record, probe_held, redact_all
from bench.summarize import load, markdown, summarize

MISSING = "not recorded"
SWARM_ARM = "tests+probes+swarm"
DECIDING = ("tests", "tests+probes")
PR_URL = re.compile(r"^https://github\.com/([^/\s]+/[^/\s]+)/pull/(\d+)$")
FAIL_KEYS = ("regressions", "new_tests_failing", "pr_unstable")
OPEN_TEST_KEYS = ("flaky", "pr_unstable_noisy")
OPEN_LABELS = ("flaky", "needs_human", "unstable_on_pr", "not_testable")
METRIC_ORDER = (
    "n_cases", "wrong_approvals", "bugs_caught", "bugs_caught_tests_miss", "false_alarms",
    "verification_coverage", "could_not_verify_or_not_run", "could_not_verify", "not_run",
    "setup_failures", "matches_expected", "runtime_s", "model_calls", "cost_usd", "caught_ids",
)
ENV_KEYS = ("harness_commit", "started_ist", "python", "platform", "sandbox_backend", "POC_REQUIRE_CONTREE")
QUOTE_LIMIT = 500


def show(value) -> str:
    """A recorded value, or the missing-field words. Nothing is filled in."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return MISSING
    if isinstance(value, str):
        return value if value.strip() else MISSING
    if isinstance(value, (int, float)):
        return str(value)
    text = json.dumps(value, sort_keys=True, default=str)
    return text if text.strip() else MISSING


def clip(text: str) -> str:
    if len(text) <= QUOTE_LIMIT:
        return text
    return text[:QUOTE_LIMIT] + "… (truncated)"


def verdict_token(result: dict) -> str:
    """The recorded verdict when the arm ran, otherwise not_run or the missing-field words."""
    if not isinstance(result, dict) or result.get("outcome") is None:
        return MISSING
    if result.get("outcome") != "ran":
        return "not_run" if result.get("outcome") == "not_run" else MISSING
    verdict = result.get("verdict")
    if verdict in VERDICTS:
        return verdict
    return MISSING


def deciding_names(arm_names: list[str]) -> list[str]:
    """Arms whose recorded verdict is the decision. The swarm arm stays out when a deciding arm exists."""
    preferred = [name for name in DECIDING if name in arm_names]
    if preferred:
        return preferred
    rest = [name for name in arm_names if name != SWARM_ARM]
    return rest or [name for name in arm_names]


def decision_line(by_arm: dict[str, dict]) -> str:
    """One plain line. The tokens are the recorded verdicts. No other words are added."""
    names = deciding_names(list(by_arm))
    if not names:
        return "Decision: not recorded."
    parts = [f"{name}={verdict_token(by_arm[name])}" for name in names]
    return "Decision: " + "; ".join(parts) + "."


def _text(value) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def tested_field(result: dict, key: str) -> str:
    tested = result.get("tested") if isinstance(result, dict) else None
    if not isinstance(tested, dict) or key not in tested:
        return MISSING
    return show(tested.get(key))


def stage_field(result: dict, key: str) -> str:
    stages = result.get("stages") if isinstance(result, dict) else None
    if not isinstance(stages, dict) or key not in stages:
        return MISSING
    return show(stages.get(key))


def identity(result: dict, record: dict | None) -> dict:
    """Repo and pull-request URL from the check record, then from the recorded command."""
    url, repo = None, None
    repo_source = None
    pr = record.get("pr") if isinstance(record, dict) and isinstance(record.get("pr"), dict) else {}
    if isinstance(record, dict):
        if _text(pr.get("url")):
            url = pr["url"].strip()
        if _text(record.get("repo")):
            repo, repo_source = record["repo"].strip(), "check record"
        elif _text(pr.get("repo")):
            repo, repo_source = pr["repo"].strip(), "check record"
    if url is None:
        cmd = result.get("command") if isinstance(result, dict) else None
        if isinstance(cmd, list):
            for i, tok in enumerate(cmd[:-1]):
                if tok == "--pr" and _text(cmd[i + 1]):
                    url = cmd[i + 1].strip()
                    break
    if repo is None and url:
        match = PR_URL.match(url)
        if match:
            repo, repo_source = match.group(1), "recorded pull request URL"
    return {
        "repo": f"{repo} ({repo_source})" if repo else MISSING,
        "pr": url or MISSING,
        "pr_href": url if url and PR_URL.match(url) else None,
    }


def load_check_record(root: Path, arm: str, case_id: str) -> dict | None:
    """The one record bench.run.find_record would read for this case and arm."""
    return find_record(root / "ops" / arm_dir_name(arm), f"bench-{case_id}")


def held_probe_quotes(record: dict | None) -> list[str] | None:
    """Quotes for probe findings that bench.run.probe_held counts. None when the record does not expose them."""
    flag = probe_held(record if isinstance(record, dict) else None)
    if flag is not True:
        return [] if flag is False else None
    quotes = []
    items = (record.get("probes") or {}).get("items") if isinstance(record, dict) else None
    if not isinstance(items, list):
        return []
    for item in items:
        if not isinstance(item, dict):
            continue
        runs = item.get("runs")
        observations = item.get("observations")
        if not isinstance(runs, dict) or not isinstance(observations, list):
            continue
        sides = {key: runs.get(key) for key in ("main", "pr")}
        if not all(isinstance(value, list) and len(value) == PROBE_RUNS for value in sides.values()):
            continue
        if not all(entry.get("ok") for entry in item.get("per_run") or [{}]):
            continue
        for obs in observations:
            if not isinstance(obs, dict):
                continue
            name = obs.get("name")
            if obs.get("state") != "differs" or obs.get("label") not in RED_LABELS:
                continue
            vals = {
                key: [entry.get(name, "<missing>") if isinstance(entry, dict) else "<missing>" for entry in value]
                for key, value in sides.items()
            }
            stable = all(len({json.dumps(x, sort_keys=True) for x in value}) == 1 for value in vals.values())
            if not stable or vals["main"][0] == vals["pr"][0]:
                continue
            quotes.append(
                f"probe {show(item.get('id'))} observation {show(name)} label {obs.get('label')}: "
                f"main={json.dumps(vals['main'][0], sort_keys=True, default=str)} "
                f"pr={json.dumps(vals['pr'][0], sort_keys=True, default=str)} "
                f"(same value on all {PROBE_RUNS} runs of each side)"
            )
    return quotes


def failing_test_quotes(record: dict | None) -> list[str] | None:
    """Failing test names from the check record's comparison. None when that block was not recorded."""
    if not isinstance(record, dict) or not isinstance(record.get("comparison"), dict):
        return None
    comparison = record["comparison"]
    if not any(key in comparison for key in FAIL_KEYS):
        return None
    messages = comparison.get("messages") if isinstance(comparison.get("messages"), dict) else {}
    quotes = []
    saw_list = False
    for key in FAIL_KEYS:
        if key not in comparison or not isinstance(comparison[key], list):
            continue
        saw_list = True
        for item in comparison[key]:
            if isinstance(item, str):
                message = messages.get(item)
                extra = f" ({clip(message.strip())})" if _text(message) else ""
                quotes.append(f"comparison.{key}: {item}{extra}")
            else:
                quotes.append(f"comparison.{key}: {clip(show(item))}")
    return quotes if saw_list else None


def _reason(record: dict | None, result: dict) -> tuple[str, str] | None:
    if isinstance(record, dict) and _text(record.get("reason")):
        return record["reason"].strip(), "check record"
    if _text(result.get("reason")):
        return result["reason"].strip(), "arm result"
    return None


def strongest_lines(record: dict | None, result: dict) -> list[str]:
    """Held probe findings, then failing test names, then the recorded reason. Quotes only."""
    lines = []
    probes = held_probe_quotes(record)
    fails = failing_test_quotes(record)
    if probes:
        lines.extend(clip(line) for line in probes)
    if fails:
        lines.extend(clip(line) for line in fails)
    if lines:
        return lines
    found = _reason(record, result)
    if found:
        text, source = found
        return [f"{source}: {clip(text)}"]
    return [MISSING]


def verified_lines(record: dict | None, result: dict) -> list[str]:
    lines = []
    found = _reason(record, result)
    lines.append(f"Recorded reason ({found[1]}): {clip(found[0])}" if found else f"Recorded reason: {MISSING}")
    probes = held_probe_quotes(record)
    if probes is None:
        lines.append(f"Probe result that held on all runs: {MISSING}")
    elif not probes:
        lines.append("Probe result that held on all runs: none")
    else:
        lines.append("Probe result that held on all runs:")
        lines.extend(clip(line) for line in probes)
    fails = failing_test_quotes(record)
    if fails is None:
        lines.append(f"Failing test names: {MISSING}")
    elif not fails:
        lines.append("Failing test names: none")
    else:
        lines.append("Failing test names:")
        lines.extend(clip(line) for line in fails)
    executed = None
    if isinstance(record, dict) and isinstance(record.get("comparison"), dict):
        executed = record["comparison"].get("executed") if "executed" in record["comparison"] else None
    if isinstance(executed, dict):
        lines.append(f"Tests executed: main={show(executed.get('main'))}, pr={show(executed.get('pr'))}")
    else:
        lines.append(f"Tests executed: {MISSING}")
    if "probe_held_all_runs" not in result or result.get("probe_held_all_runs") is None:
        lines.append(f"probe_held_all_runs: {MISSING}")
    else:
        lines.append(f"probe_held_all_runs: {show(result.get('probe_held_all_runs'))}")
    return lines


def inferred_lines(record: dict | None) -> list[str]:
    """Model text stored on the check record. Not executed evidence."""
    if not isinstance(record, dict) or "explanation" not in record or record.get("explanation") is None:
        return [MISSING]
    explanation = record["explanation"]
    if isinstance(explanation, str):
        return [clip(explanation)] if explanation.strip() else [MISSING]
    if not isinstance(explanation, dict):
        return [clip(show(explanation))]
    lines = []
    if "status" in explanation:
        lines.append(f"status: {show(explanation.get('status'))}")
    lines.append(clip(explanation["text"].strip()) if _text(explanation.get("text")) else f"text: {MISSING}")
    quotes = explanation.get("quotes")
    if isinstance(quotes, list) and quotes:
        for quote in quotes:
            lines.append("quote: " + clip(quote if isinstance(quote, str) else show(quote)))
    if _text(explanation.get("why")):
        lines.append("why: " + clip(explanation["why"].strip()))
    return lines or [MISSING]


def _role_line(role: dict) -> str:
    bits = [f"role {show(role.get('role'))}", f"status {show(role.get('status'))}"]
    if role.get("labels") is not None:
        bits.append("labels " + clip(show(role.get("labels"))))
    if role.get("notes") is not None:
        bits.append("notes " + clip(show(role.get("notes"))))
    if _text(role.get("note")):
        bits.append("note " + clip(role["note"].strip()))
    return "; ".join(bits)


def advisory_lines(record: dict | None, swarm: dict | None) -> list[str]:
    """Swarm notes and the advisory arm's recorded verdict. They are not the decision."""
    lines = []
    if swarm is not None:
        lines.append(f"Advisory arm {SWARM_ARM} recorded verdict: {verdict_token(swarm)}")
        if _text(swarm.get("reason")):
            lines.append("Advisory arm reason: " + clip(swarm["reason"].strip()))
    recorded = False
    if isinstance(record, dict) and "swarm" in record and record.get("swarm") is not None:
        lines.append(f"swarm: {show(record.get('swarm'))}")
        recorded = True
    agents = record.get("agents") if isinstance(record, dict) else None
    if isinstance(agents, dict):
        recorded = True
        if "status" in agents:
            lines.append(f"agents status: {show(agents.get('status'))}")
        if _text(agents.get("note")):
            lines.append("agents note: " + clip(agents["note"].strip()))
        roles = agents.get("roles")
        if isinstance(roles, list):
            for role in roles:
                if isinstance(role, dict):
                    lines.append(_role_line(role))
        elif "roles" in agents:
            lines.append(f"agents roles: {MISSING}")
    elif isinstance(record, dict) and "agents" in record:
        recorded = True
        lines.append(f"agents: {show(agents)}")
    if not lines and not recorded:
        return [MISSING]
    return lines


def uncertainty_lines(record: dict | None) -> list[str] | None:
    """Open items the check record actually stores. None when the record has none of those fields."""
    if not isinstance(record, dict):
        return None
    lines = []
    saw = False
    comparison = record.get("comparison") if isinstance(record.get("comparison"), dict) else None
    if isinstance(comparison, dict):
        for key in OPEN_TEST_KEYS:
            if key not in comparison or not isinstance(comparison[key], list):
                continue
            saw = True
            for item in comparison[key]:
                lines.append(f"comparison.{key}: {clip(item if isinstance(item, str) else show(item))}")
    probes = record.get("probes") if isinstance(record.get("probes"), dict) else None
    items = probes.get("items") if isinstance(probes, dict) else None
    if isinstance(items, list):
        saw = True
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("observations"), list):
                continue
            for obs in item["observations"]:
                if isinstance(obs, dict) and obs.get("label") in OPEN_LABELS:
                    lines.append(
                        f"probe {show(item.get('id'))} observation {show(obs.get('name'))} "
                        f"label {obs.get('label')} state {show(obs.get('state'))}"
                    )
    helper = record.get("demo_helper") if isinstance(record.get("demo_helper"), dict) else None
    limits = helper.get("limitations") if isinstance(helper, dict) else None
    if isinstance(limits, list):
        saw = True
        for item in limits:
            lines.append("limitation: " + clip(item if isinstance(item, str) else show(item)))
    if not saw:
        return None
    return lines


def unverified_lines(record: dict | None, result: dict) -> list[str]:
    lines = []
    if result.get("outcome") == "not_run":
        why = result.get("not_run_why")
        if isinstance(why, list) and why:
            lines.extend(f"not run: {clip(item if isinstance(item, str) else show(item))}" for item in why)
        elif _text(why):
            lines.append("not run: " + clip(why.strip()))
        else:
            lines.append(f"not run: {MISSING}")
        tail = result.get("stderr_tail")
        if _text(tail):
            lines.append("stderr_tail: " + clip(tail.strip()))
        elif "stderr_tail" not in result:
            lines.append(f"stderr_tail: {MISSING}")
    if result.get("outcome") == "ran" and result.get("verdict") == "could_not_verify":
        found = _reason(record, result)
        lines.append(f"could-not-verify reason: {clip(found[0])}" if found else f"could-not-verify reason: {MISSING}")
    else:
        lines.append("could-not-verify reason: none")
    open_items = uncertainty_lines(record)
    if open_items is None:
        lines.append(f"unresolved uncertainties: {MISSING}")
    elif not open_items:
        lines.append("unresolved uncertainties: none")
    else:
        lines.append("unresolved uncertainties:")
        lines.extend(open_items)
    return lines


def runtime_cell(result: dict) -> str:
    bits = []
    if isinstance(result.get("wall_seconds"), (int, float)) and not isinstance(result.get("wall_seconds"), bool):
        bits.append(f"wall_seconds={result['wall_seconds']}")
    if "check_duration_s" in result and result.get("check_duration_s") is not None:
        bits.append(f"check_duration_s={show(result.get('check_duration_s'))}")
    return ", ".join(bits) if bits else MISSING


def model_cell(result: dict) -> str:
    model = result.get("model") if isinstance(result.get("model"), dict) else None
    if not isinstance(model, dict):
        return MISSING
    bits = []
    for key in ("ai_calls", "failed_ai_calls", "input_tokens", "output_tokens", "provider"):
        if key in model and model.get(key) is not None:
            bits.append(f"{key}={show(model.get(key))}")
    return ", ".join(bits) if bits else MISSING


def cost_cell(result: dict) -> str:
    model = result.get("model") if isinstance(result.get("model"), dict) else None
    if not isinstance(model, dict) or "cost_usd" not in model or model.get("cost_usd") is None:
        return MISSING
    return show(model.get("cost_usd"))


def format_metric(key: str, value) -> str:
    """One summary.json metric, with the n that object recorded."""
    if key == "n_cases":
        return f"n={show(value)}"
    if isinstance(value, dict) and "count" in value and "n" in value:
        rate = value.get("rate")
        rate_text = "n/a (n=0)" if rate is None and value.get("n") == 0 else show(rate)
        return f"count={show(value.get('count'))} n={show(value.get('n'))} rate={rate_text}"
    if isinstance(value, dict) and "total" in value:
        if "n" in value:
            n_text = show(value.get("n"))
        elif "n_reported" in value:
            n_text = show(value.get("n_reported"))
        else:
            n_text = MISSING
        return f"total={show(value.get('total'))} n={n_text}"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"count={show(value)}"
    return show(value)


def metric_rows(summary: dict) -> list[list[str]]:
    rows = []
    arms = summary.get("arms") if isinstance(summary.get("arms"), dict) else {}
    for arm, metrics in arms.items():
        if not isinstance(metrics, dict):
            rows.append([arm, "metrics", MISSING])
            continue
        keys = [key for key in METRIC_ORDER if key in metrics]
        keys += [key for key in metrics if key not in keys]
        for key in keys:
            rows.append([arm, key, format_metric(key, metrics[key])])
    return rows


def environment_rows(meta: dict) -> list[list[str]]:
    env = meta.get("environment")
    if not isinstance(env, dict):
        return [["environment", MISSING]]
    rows = [[key, show(env.get(key)) if key in env else MISSING] for key in ENV_KEYS]
    keys = env.get("keys")
    if isinstance(keys, dict):
        rows.extend([f"key {name}", show(keys[name])] for name in sorted(keys))
    elif "keys" in env:
        rows.append(["keys", show(keys)])
    else:
        rows.append(["keys", MISSING])
    return rows


def _arm_order(meta: dict, arms: dict[str, list]) -> list[str]:
    names = list(meta["arms"]) if isinstance(meta.get("arms"), dict) else []
    for name in arms:
        if name not in names:
            names.append(name)
    return names


def _case_sample(meta_case: dict, by_arm: dict[str, dict]) -> bool:
    if meta_case.get("fixture") is True:
        return True
    return any(isinstance(result, dict) and result.get("fixture") is True for result in by_arm.values())


def _case_view(root: Path, meta_case: dict, names: list[str], by_arm: dict[str, dict]) -> dict:
    ordered = {name: by_arm[name] for name in deciding_names(names)}
    records = {name: load_check_record(root, name, meta_case["id"]) for name in names}
    swarm = by_arm.get(SWARM_ARM)
    text_order = [name for name in (*DECIDING, SWARM_ARM) if name in names]
    text_order += [name for name in names if name not in text_order]
    who = []
    for name in names:
        found = identity(by_arm[name], records.get(name))
        who.append([
            name, found["repo"], found["pr"], tested_field(by_arm[name], "base_sha"),
            tested_field(by_arm[name], "pr_sha"), tested_field(by_arm[name], "pr_side"), found["pr_href"],
        ])
    advisory = []
    if swarm is not None:
        advisory.append((SWARM_ARM, advisory_lines(records.get(SWARM_ARM), swarm)))
    for name in text_order:
        if name == SWARM_ARM:
            continue
        advisory.append((name, advisory_lines(records.get(name), None)))
    return {
        "id": show(meta_case.get("id")),
        "sample": _case_sample(meta_case, by_arm),
        "decision": decision_line(ordered if ordered else {name: by_arm[name] for name in deciding_names(list(by_arm))}),
        "strongest": [(name, strongest_lines(records.get(name), by_arm[name])) for name in text_order],
        "identity": who,
        "arms": [
            [
                name,
                verdict_token(by_arm[name]),
                stage_field(by_arm[name], "install"),
                stage_field(by_arm[name], "tests"),
                stage_field(by_arm[name], "probes"),
                stage_field(by_arm[name], "infra"),
                runtime_cell(by_arm[name]),
                model_cell(by_arm[name]),
                cost_cell(by_arm[name]),
            ]
            for name in names
        ],
        "verified": [(name, verified_lines(records.get(name), by_arm[name])) for name in text_order],
        "inferred": [(name, inferred_lines(records.get(name))) for name in text_order],
        "advisory": advisory,
        "unverified": [(name, unverified_lines(records.get(name), by_arm[name])) for name in text_order],
    }


def build(root: Path) -> dict:
    """Report data from one results folder. Summaries are bench.summarize's own objects."""
    root = Path(root)
    meta = json.loads((root / "run_meta.json").read_text())
    arms = load(root)
    summary = summarize(arms)
    names = _arm_order(meta, arms)
    index = {arm: {row["case_id"]: row for row in rows} for arm, rows in arms.items()}
    cases = []
    for meta_case in meta.get("cases") or []:
        if not isinstance(meta_case, dict) or "id" not in meta_case:
            continue
        by_arm = {}
        for name in names:
            found = index.get(name, {}).get(meta_case["id"])
            by_arm[name] = found if isinstance(found, dict) else {
                "case_id": meta_case["id"], "arm": name, "outcome": "not_run", "verdict": None,
                "not_run_why": ["no result file"],
            }
        cases.append(_case_view(root, meta_case, names, by_arm))
    sample = bool(summary.get("fixture_results")) or any(case["sample"] for case in cases)
    return {
        "sample": sample,
        "summary_md": markdown(summary),
        "metrics": metric_rows(summary),
        "uplift": summary.get("probe_uplift") if isinstance(summary.get("probe_uplift"), dict) else None,
        "environment": environment_rows(meta if isinstance(meta, dict) else {}),
        "cases": cases,
    }


def _md_cell(value) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def _md_table(headers: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join(_md_cell(cell) for cell in row) + " |")
    return out


def _md_arm_blocks(blocks: list[tuple[str, list[str]]]) -> list[str]:
    lines = []
    for name, body in blocks:
        lines.append(f"**{name}**")
        lines.append("")
        lines.extend(body)
        lines.append("")
    return lines


def _id_list(value) -> str:
    if not isinstance(value, list):
        return MISSING
    return ", ".join(str(item) for item in value) if value else "none"


def _uplift_rows(uplift: dict) -> list[list[str]]:
    gained = uplift.get("caught_by_probes_not_tests")
    lost = uplift.get("caught_by_tests_not_probes")
    compared = "regression_cases_compared" in uplift
    return [
        ["Caught by tests+probes but not tests-only", _id_list(gained)],
        ["Caught by tests-only but not tests+probes", _id_list(lost)],
        ["Comparable regression cases", show(uplift.get("regression_cases_compared")) if compared else MISSING],
    ]


def _uplift_md(uplift: dict | None) -> list[str]:
    if not isinstance(uplift, dict):
        return ["Probe uplift: not recorded", ""]
    excluded = uplift.get("excluded")
    rows = _uplift_rows(uplift)
    lines = ["### Probe uplift", ""]
    lines.extend(_md_table(["Field", "Value"], rows))
    lines.append("")
    lines.append("Excluded cases:")
    lines.append("")
    if not isinstance(excluded, dict):
        lines.append(MISSING)
    elif not excluded:
        lines.append("none")
    else:
        lines.extend(_md_table(["Case", "Reason"], [[cid, why] for cid, why in excluded.items()]))
    lines.append("")
    return lines


def render_markdown(doc: dict) -> str:
    lines = ["# Benchmark evidence report", ""]
    if doc.get("sample"):
        lines.extend(["SAMPLE", ""])
    lines.append("The decision line repeats the recorded verdict of the tests-only arm and the tests+probes arm.")
    lines.append("")
    lines.extend(["## Summary", "", doc.get("summary_md") or MISSING, ""])
    lines.extend(["### Metrics", ""])
    lines.extend(_md_table(["Arm", "Metric", "Recorded"], doc.get("metrics") or []))
    lines.append("")
    lines.extend(_uplift_md(doc.get("uplift")))
    lines.extend(["## Run metadata", ""])
    lines.extend(_md_table(["Field", "Recorded"], doc.get("environment") or []))
    lines.append("")
    for case in doc.get("cases") or []:
        lines.extend([f"## Case {case['id']}", ""])
        if case.get("sample"):
            lines.extend(["SAMPLE", ""])
        lines.extend([case["decision"], ""])
        lines.extend(["### Strongest supporting evidence", "", "From executed evidence.", ""])
        lines.extend(_md_arm_blocks(case["strongest"]))
        lines.extend(["### Recorded facts", ""])
        lines.extend(_md_table(
            ["Arm", "Repo", "Pull request", "Tested base SHA", "Tested PR SHA", "PR side"],
            [row[:6] for row in case["identity"]],
        ))
        lines.append("")
        lines.extend(_md_table(
            ["Arm", "Verdict", "Install", "Tests", "Probes", "Infra", "Runtime", "Model calls", "Cost USD"],
            case["arms"],
        ))
        lines.append("")
        lines.extend(["### Verified behaviour", "", "Executed evidence from the check record and the arm result.", ""])
        lines.extend(_md_arm_blocks(case["verified"]))
        lines.extend(["### Inferred explanation", "", "Model text. Not executed evidence.", ""])
        lines.extend(_md_arm_blocks(case["inferred"]))
        lines.extend(["### Advisory notes", "", "Swarm notes. Advisory only.", ""])
        lines.extend(_md_arm_blocks(case["advisory"]))
        lines.extend(["### Unverified / not run", "", "Not run, could-not-verify reasons, and unresolved uncertainties.", ""])
        lines.extend(_md_arm_blocks(case["unverified"]))
    return "\n".join(lines).rstrip() + "\n"


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _html_table(headers: list[str], rows: list[list]) -> str:
    head = "".join(f"<th>{_esc(cell)}</th>" for cell in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{_esc(cell)}</td>" for cell in row) + "</tr>")
    return "<table><thead><tr>" + head + "</tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def _html_identity(rows: list[list]) -> str:
    head = ["Arm", "Repo", "Pull request", "Tested base SHA", "Tested PR SHA", "PR side"]
    body = []
    for row in rows:
        arm, repo, pr, base, pr_sha, side, href = row
        pr_cell = f'<a href="{_esc(href)}">{_esc(pr)}</a>' if href else _esc(pr)
        cells = [_esc(arm), _esc(repo), pr_cell, _esc(base), _esc(pr_sha), _esc(side)]
        body.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    head_html = "".join(f"<th>{_esc(cell)}</th>" for cell in head)
    return "<table><thead><tr>" + head_html + "</tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def _html_blocks(blocks: list[tuple[str, list[str]]]) -> str:
    parts = []
    for name, body in blocks:
        items = "".join(f"<li>{_esc(line)}</li>" for line in body)
        parts.append(f"<h3>{_esc(name)}</h3><ul>{items}</ul>")
    return "".join(parts)


def _uplift_html(uplift: dict | None) -> str:
    if not isinstance(uplift, dict):
        return "<h2>Probe uplift</h2><p>Probe uplift: not recorded</p>"
    excluded = uplift.get("excluded")
    table = _html_table(["Field", "Value"], _uplift_rows(uplift))
    if not isinstance(excluded, dict):
        excluded_html = f"<p>{_esc(MISSING)}</p>"
    elif not excluded:
        excluded_html = "<p>none</p>"
    else:
        excluded_html = _html_table(["Case", "Reason"], [[cid, why] for cid, why in excluded.items()])
    return "<h2>Probe uplift</h2>" + table + "<h3>Excluded cases</h3>" + excluded_html


_CSS = """
body { font-family: Georgia, "Times New Roman", serif; max-width: 980px; margin: 2rem auto; padding: 0 1rem;
       color: #1a1a1a; line-height: 1.45; }
h1, h2, h3 { line-height: 1.25; }
.sample { border: 2px solid #8a5a00; background: #fff6df; padding: 0.4rem 0.7rem; font-weight: bold; }
.decision { border-left: 4px solid #1a1a1a; padding: 0.3rem 0.8rem; font-weight: bold; }
table { border-collapse: collapse; width: 100%; margin: 0.6rem 0 1.2rem; }
th, td { border: 1px solid #ccc; padding: 0.3rem 0.45rem; text-align: left; vertical-align: top; }
th { background: #f3f3f3; }
pre { white-space: pre-wrap; background: #f7f7f7; padding: 0.8rem; border: 1px solid #ddd; }
section { margin-top: 1.4rem; }
"""


def render_html(doc: dict) -> str:
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Benchmark evidence report</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        "<h1>Benchmark evidence report</h1>",
    ]
    if doc.get("sample"):
        parts.append('<p class="sample">SAMPLE</p>')
    parts.append("<p>The decision line repeats the recorded verdict of the tests-only arm and the tests+probes arm.</p>")
    parts.append("<h2>Summary</h2>")
    parts.append("<pre>" + _esc(doc.get("summary_md") or MISSING) + "</pre>")
    parts.append("<h2>Metrics</h2>")
    parts.append(_html_table(["Arm", "Metric", "Recorded"], doc.get("metrics") or []))
    parts.append(_uplift_html(doc.get("uplift")))
    parts.append("<h2>Run metadata</h2>")
    parts.append(_html_table(["Field", "Recorded"], doc.get("environment") or []))
    for case in doc.get("cases") or []:
        parts.append("<section>")
        parts.append(f"<h2>Case {_esc(case['id'])}</h2>")
        if case.get("sample"):
            parts.append('<p class="sample">SAMPLE</p>')
        parts.append(f'<p class="decision">{_esc(case["decision"])}</p>')
        parts.append("<h2>Strongest supporting evidence</h2><p>From executed evidence.</p>")
        parts.append(_html_blocks(case["strongest"]))
        parts.append("<h2>Recorded facts</h2>")
        parts.append(_html_identity(case["identity"]))
        parts.append(_html_table(
            ["Arm", "Verdict", "Install", "Tests", "Probes", "Infra", "Runtime", "Model calls", "Cost USD"],
            case["arms"],
        ))
        parts.append("<h2>Verified behaviour</h2><p>Executed evidence from the check record and the arm result.</p>")
        parts.append(_html_blocks(case["verified"]))
        parts.append("<h2>Inferred explanation</h2><p>Model text. Not executed evidence.</p>")
        parts.append(_html_blocks(case["inferred"]))
        parts.append("<h2>Advisory notes</h2><p>Swarm notes. Advisory only.</p>")
        parts.append(_html_blocks(case["advisory"]))
        parts.append("<h2>Unverified / not run</h2><p>Not run, could-not-verify reasons, and unresolved uncertainties.</p>")
        parts.append(_html_blocks(case["unverified"]))
        parts.append("</section>")
    parts.append("</body></html>")
    return "\n".join(parts) + "\n"


def write_report(root: Path, out: Path | None = None) -> tuple[Path, Path]:
    """Build the report, redact it, and write evidence.md and evidence.html."""
    root = Path(root)
    out = Path(out) if out is not None else root
    doc = redact_all(build(root))
    md = redact_all(render_markdown(doc))
    page = redact_all(render_html(doc))
    out.mkdir(parents=True, exist_ok=True)
    md_path, html_path = out / "evidence.md", out / "evidence.html"
    md_path.write_text(md)
    html_path.write_text(page)
    return md_path, html_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", help="results folder written by bench.run (contains run_meta.json)")
    ap.add_argument("--out", default=None, help="directory for evidence.md and evidence.html (default: the results folder)")
    args = ap.parse_args(argv)
    md_path, html_path = write_report(Path(args.results), Path(args.out) if args.out else None)
    print(md_path)
    print(html_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
