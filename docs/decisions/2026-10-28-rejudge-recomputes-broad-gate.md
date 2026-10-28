# Re-judging recomputes the broad-claims gate, and never releases a saved hold

A broad "nothing else changes" claim needs at least 3 varied inputs (poc/broad_claims.py). That gate was applied only in a live run and saved on the record, so re-judging trusted the saved copy, and product-check records written before the gate existed skipped it.

Re-judging a record marked as a product check now recomputes the gate from the re-judged probe results with current code and keeps the union of the saved and the recomputed holds: a claim held back when the record was written stays held back. So the gate can only lower verified to could_not_verify, never raise a verdict, and never produces verified. The record's note is refreshed.

Scope: only records with product_check set. Records without that key (older study-route and benchmark records) are re-judged as before, with no broad-claims gate.
