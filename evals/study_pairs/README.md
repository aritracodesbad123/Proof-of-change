# Main-study pairs

329 candidates entered expansion. 9 were skipped there, before gathering: 8 on the human side (7 empty patches, 1 not a diff) and 1 on the agent side (not a diff). Those 9 are in `expansion-skips.csv`. The counts are in `expansion-stats.json`.

320 candidates reached the gatherer. 92 matched. 228 were excluded because the two pull requests do not change a file in common (`no_shared_file`). The list order uses seed 20261020.

- `main-study-pairs.json` SHA-256: `00401f1fd6e72a820085fc66aa1ce1638c9e314ce17ca5c4aa192201e3566c54`
- `evals/study_pair_rules.json` SHA-256: `2a3ed899da1652ec7bcb9e72e8e7808c9cbb6494418de35358fb7ea8e4e6c5a1`

Tuning cases were not excluded by any rule. A check after the run found none of them, or their repositories, among the candidates.
