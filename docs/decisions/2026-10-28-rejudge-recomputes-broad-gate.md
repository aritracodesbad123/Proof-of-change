# Re-judging recomputes the broad-claims gate

A broad "nothing else changes" claim needs at least 3 varied inputs (poc/broad_claims.py). That gate was applied only in a live run and saved on the record, so re-judging trusted the saved copy, and records written before the gate existed (or under an older minimum) skipped it.

Re-judging now recomputes the gate on the product route from the recomputed probe results with current code, replaces any saved copy, and refreshes the record's note. The study route is unchanged. The gate only lowers verified to could_not_verify, so this never produces verified.
