# chosen PRs

## 1. demo

- **Repo:** https://github.com/acme/widget (default branch `main`)
- **Open PR:** #12, "Fix thing"
  - Head SHA: `0123456789abcdef0123456789abcdef01234567`
**Expected Proof-of-Change verdict: `needs attention` (low severity)**
- Install: `pip install -e ".[x]" pytest hypothesis`
- Test (subset, fast): `pytest tests/test_a.py tests/test_b.py -n 4 -k "not slow"`

## 2. narwhals

- **Repo:** https://github.com/narwhals-dev/narwhals (default branch `main`)
- **Open PR:** #4062, "division by zero"
  - Head SHA: `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`
**Expected Proof-of-Change verdict: `verified`**

Setup notes:
- Install: `pip install -e ".[dev]"`
- Test: `pytest tests/expr_and_series/division_by_zero_test.py`, wider `pytest tests -n 4`

## 3. networkx (graph algorithms, large)

- **Repo:** https://github.com/networkx/networkx (default branch `main`)
- Install: `pip install -e ".[test]" pytest`

### Primary PR: #8946, "Fix issue #2"
  - URL: https://github.com/networkx/networkx/pull/8946
  - Head SHA: `56e4499e8f61da4180e2451e8140acf459cf95cc` (branch topic)
**Expected Proof-of-Change verdict: `verified`**

### Secondary PR (if time allows): #8862, "ENH: ..."
  - Head SHA: `636941793808cba5f84239470afcac2cf336b3eb`
- **Expected verdict:** `verified` **only if** the new tests cover the change
