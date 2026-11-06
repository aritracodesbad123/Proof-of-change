# A contradicted preservation part that is the proven change

## What changed

A claim that says behaviour is preserved, and that names several results exactly, no longer raises needs
attention for one of those results when that result's change is the count an intended differs claim already
proved. The observation keeps its contradicted-same label. The reason lists it as an invalid preservation
claim. No stored record is rewritten.

## Why

A recorded check of a rotation fix carried a broad preservation claim: the method returns True exactly when
at least one condition evaluates to True, preserving the contract. The claim named two returns. The first
stayed True. The second went from True to False. A differs claim's count of true returns went from 2 to 1,
which is those two returns added up. The second return changing is the bug the change removes, so scoring it
as a broken preservation claim was a false alarm.

The same shape must not clear a real miss. A second call that should rotate, and does not, still needs
attention. An unrelated return that flips, with no claim, still needs attention. A preservation claim whose
parts do not add up to the proven count still needs attention. So does a claim whose every named part
changed, a preservation claim that has any wildcard cover, a count proved on a different probe, and a
claim that only says something is "still" rejected.

## Decision

- The check runs where probe findings are turned into the verdict, after the claims and the observations are
  known. Claim clean-up cannot see which side changed, so it does not decide this.
- The preservation claim expects "same", and its text says the behaviour is preserved: preserved, unchanged,
  as before, stays the same, or remains the same. "Still" on its own is not that wording.
- It names at least two observations, and every cover is an exact name. One wildcard cover rejects the
  claim. The exact names are not kept after a wildcard is dropped. At least one named result stays the same
  and is proven. At least one differs and is a contradicted same claim. Every named result is a boolean. A
  claim whose every named result changed is left alone.
- A different claim on the same probe expects a difference and is proven by an observation it names exactly.
  That observation's two numbers equal the count of True among the preservation claim's named results, on
  each side. A count on another probe does not qualify, including when that probe reuses the claim id. The
  differing parts are then that proven change.
- Those parts are left out of the observations that raise needs attention. The reason names them and says
  "invalid preservation claim; this part is the intended change already proven". The label stays
  false_claim. They are not marked as an unclaimed difference, so they do not hold a check at could not
  verify for that reason.
- An observation that is not one of those exact names is not excused. A count that does not match is not a
  link. Nothing in the rule names a repository or a pull request.
- Stored records stay as they were. This note's re-judge is a separate reading. It is not a reissued verdict
  and it is not a new verified tally.

## Alternatives and tradeoffs

- Excusing every contradicted same claim once any differs claim is proven would clear real misses. A set of
  proven differs claims plus one unrelated difference is not a pass.
- Treating "still" as preservation wording would pull in a claim that old broken behaviour is "still"
  rejected. That wording is not this rule.
- Marking the part as an unclaimed difference would cap a clean check at could not verify for the wrong
  reason. The label stays a contradicted same claim, and the reason says why it does not raise attention.
- Asking a model to re-read the claims is not required. The probe plan already names the parts and the count.
  No live model call is part of this change.

## What it means for you

A check with this shape no longer says needs attention only because that one preservation part changed. The
reason names the part. A real disagreement, including one the count does not explain, still needs attention.
Published records are unchanged. A later live run is what would write a new record. This re-judge does not.

## Offline proof

Parent is `d7a7bdf9e3f74d679aed29a0e7a7e3c55a1ab085`. The runs branch was fetched as
`4d3cd3009685f37874ac44b7590e08d3c2225c84` and read with `git archive`. It was not checked out, and nothing in
those records was executed. `scripts/rejudge_preservation.py` judges each `record.json` with the parent code
and with this code, from the saved probe runs only.

Runs branch, 52 `record.json` files. 41 judged, 40 unchanged, 1 changed, 11 not judged, 0 errors.

Requiring every preservation cover to be exact, and the proven count to be on the same probe, was re-judged
on these same files. The only change is still the one record below. No cross-probe count and no mixed
wildcard cleared a stored verdict.

The one change is Delgan/loguru #1515 at
`runs/2026-11-06/27fde03/loguru-1515/record.json`
(`https://github.com/aritracodesbad123/Proof-of-change/tree/runs/runs/2026-11-06/27fde03/loguru-1515`).
Stored verdict needs attention. Parent re-judge needs attention, because `c2.ret_msg2` differs although the
preservation claim says it does not. Candidate re-judge verified: that observation is listed as an invalid
preservation claim and is no longer in the flagged set. The other loguru #1515 records on the branch do not
change (could not verify, or no probe items). The stored file is not edited. This candidate reading is not a
published verdict and is not added to a verified tally.

In-repo `record.json` files, 84. 44 judged, 44 unchanged, 0 changed, 40 not judged, 0 errors. Those files do
not include the loguru #1515 record above.

Named records:

- Textualize/rich #3163, on the runs branch: stored verified, parent verified, candidate verified. It does
  not lose needs attention, because the parent re-judge is not needs attention.
- python-barcode #162 is not a stored `record.json` in either set. `tests/test_invalid_preservation.py`
  re-judges `tests/fixtures/same_input_guard/barcode-162.json`. The verdict stays needs attention.
- urllib3 #5278 is not in either set. No reading of it is claimed, and no false-positive tally is claimed
  for it.
- mahmoud/boltons #732: the record that flags `c8.error` ("still rejected") stays needs attention. The other
  stays could not verify.
- python-jsonschema/jsonschema #1515 stays needs attention.

Not judged on the runs branch, because the file has no probe items or no verdict. Each is listed so it is
not a silent skip: jsonschema #1459, loguru #1531, urllib3 #5352, four `o/lib` #5 records, `o/lib` #7,
scikit-learn #29677 (no verdict), and two loguru #1515 records whose probe item list is empty
(2026-11-06/4050401 and 2026-11-06/f4f36d9).

Not judged in the repo: 40 files with no probe items, under `benchmarks/`, `replay/checks/`,
`reports/hackathon-ablation-nebius/`, and `tests/fixtures/claim_autofill/rich-4147-live191`. The script
prints each path.

`tests/test_invalid_preservation.py` uses a general fixture, with no repository name. The second return
going from True to False, while the true-return count goes from 2 to 1, does not raise needs attention. The
second call that should rotate and stays false still needs attention. An unrelated flip still needs
attention. Proven differs claims plus one difference the count does not explain still need attention. A
"still rejected" claim, a wildcard cover, a claim whose every part changed, and a count that does not move
with the flip, all still need attention.
