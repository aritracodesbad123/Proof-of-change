"""The one final verdict of a PR record, read by the run log, the reviewer reports, the summary and record.json.

A run applies every gate once when it writes the record (ops/daily_run.gate: coverage gate, AI-probe gate,
broken-probe gate, no-evidence gate, advisory gate, probe-rewrite cap). The record's ``verdict`` and ``reason`` are
then final, and every view must show exactly them. Re-applying only the coverage gate in a view would restore the
verdict from before the later gates and silently disagree with record.json.

Only a record written before the gates existed (no ``coverage_gate`` block) is gated here, so old reports can still
be rebuilt with the current rules."""
from __future__ import annotations

LABELS = {"verified": "VERIFIED", "needs_attention": "NEEDS ATTENTION",
          "could_not_verify": "COULD NOT VERIFY", "no_code_change": "NO CODE CHANGE"}


def is_final(rec: dict) -> bool:
    """True when the run that wrote this record already applied every gate."""
    return isinstance(rec.get("coverage_gate"), dict)


def final(rec: dict) -> dict:
    """The record with its final verdict and reason. Gated records are returned unchanged (a copy).

    A placeholder (a check that started but did not finish, poc/pdf_always.py) is always could_not_verify."""
    if rec.get("placeholder") or rec.get("record_kind") == "placeholder":
        from poc.pdf_always import PLACEHOLDER_REASON
        return dict(rec, verdict="could_not_verify", reason=rec.get("reason") or PLACEHOLDER_REASON)
    if is_final(rec):
        return dict(rec)
    from poc import coverage_gate
    before = rec.get("verdict_before_ai_probe_gate")
    downgraded = bool(before and before != rec.get("verdict")) or (
        rec.get("verdict") == "could_not_verify" and "no AI-written probe" in (rec.get("reason") or ""))
    out = coverage_gate.apply(rec)
    if downgraded:
        from ops.daily_run import ai_probe_gate
        out = ai_probe_gate(out)
    return out


def label(verdict: str | None) -> str:
    return LABELS.get(verdict or "", str(verdict or "").upper())


def disagreements(pairs) -> list[str]:
    """pairs: (record as stored in record.json, label shown in the report/summary). One line per disagreement."""
    out = []
    for rec, shown in pairs:
        want = label(final(rec).get("verdict"))
        if shown != want:
            tag = f"{rec.get('repo') or (rec.get('pr') or {}).get('repo')}#" \
                  f"{(rec.get('pr') or {}).get('number') if isinstance(rec.get('pr'), dict) else rec.get('pr')}"
            out.append(f"{tag}: record.json says {want} but the report shows {shown}")
    return out
