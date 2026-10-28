# One final verdict for the record, the report and the summary

Status: proposed

The record, the report and the summary now read one final verdict from one place (`poc/final_verdict.py`). A
gated record is read as stored; an older record without the gate result is gated once on read. The self-check
fails the run when the report and a record disagree, except for a deliberate trust override (failed replay or
failed checks), which is marked in the summary.

The "without rewrite" re-derivation now keeps the stored advisory mark for an observation no claim mentions, so a
note-only difference no longer lowers the verdict. A replay test of a stored record covers this. A rejudge over
the stored records only lowered or kept verdicts; none went up.
