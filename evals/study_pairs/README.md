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

`pair-labels-v2.json` has one entry per pair (`repo`, `agent_pr`, `human_pr`, `label`, `pypi_project`, `found_by`). Its SHA-256 is `5141a00db045be14ce39ec2caba743a3913c8374e83df9d55432d14659dd55b4`.

Revised labels: library 62, non_library 30, unknown 0.

Nine pairs changed from `non_library` in the first labelling to `library` under the revised rule. No pair moved the other way.

- `getsentry/sentry-python` agent 4476, human 4485: `sentry-sdk`, found in `setup.py`
- `project-numina/kimina-lean-server` agent 53, human 43: `kimina-client`, found in `pyproject.toml`
- `Uberi/speech_recognition` agent 846, human 847: `SpeechRecognition`, found in `pyproject.toml`
- `strawberry-graphql/strawberry` agent 3921, human 3923: `strawberry-graphql`, found in `pyproject.toml`
- `Uberi/speech_recognition` agent 845, human 843: `SpeechRecognition`, found in `pyproject.toml`
- `getzep/graphiti` agent 939, human 931: `graphiti-core`, found in `pyproject.toml`
- `Stable-Baselines-Team/stable-baselines3-contrib` agent 307, human 318: `sb3_contrib`, found in `setup.py`
- `microsoft/Olive` agent 1915, human 1919: `olive-ai`, found in `setup.py`
- `getzep/graphiti` agent 924, human 927: `graphiti-core`, found in `pyproject.toml`

Tuning cases were not excluded by any rule. A check after the run found none of them, or their repositories, among the candidates.
