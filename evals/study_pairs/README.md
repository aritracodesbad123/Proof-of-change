# Main-study pairs

329 candidates entered expansion. 9 were skipped there, before gathering: 8 on the human side (7 empty patches, 1 not a diff) and 1 on the agent side (not a diff). Those 9 are in `expansion-skips.csv`. The counts are in `expansion-stats.json`.

320 candidates reached the gatherer. 92 matched. 228 were excluded because the two pull requests do not change a file in common (`no_shared_file`). The list order uses seed 20261020.

- `main-study-pairs.json` SHA-256: `00401f1fd6e72a820085fc66aa1ce1638c9e314ce17ca5c4aa192201e3566c54`
- `evals/study_pair_rules.json` SHA-256: `2a3ed899da1652ec7bcb9e72e8e7808c9cbb6494418de35358fb7ea8e4e6c5a1`
- `library_label_rule.md` SHA-256: `f4e417c195184355b132544ac543c7f6c3d4c1d903637a5d74a6a82b08a01777`
- `library_label_rule_v2.md` SHA-256: `d9f380fd596a191c6be789f2e8b59411a0c5d351f28c5b1f4b1e093614ae73ee`

`library_label_rule.md` and `pair-labels.json` stay as the first labelling. The revised rule is `library_label_rule_v2.md`, recorded here before it is applied.

All 92 pairs stay in the list. The scope is Python repositories. Each repository gets a descriptive label from `library_label_rule.md`. The label does not add or remove a pair.

`pair-labels.json` has one entry per pair (`repo`, `agent_pr`, `human_pr`, `label`). Its SHA-256 is `12b9a2f2c2a7adb3149f58e2ff07a671177094dccbdfc8ef3b0bff1cb61833c1`.

Labels: library 53, non_library 39, unknown 0.

Tuning cases were not excluded by any rule. A check after the run found none of them, or their repositories, among the candidates.
