# Benchmark tooling

Tools for running Proof-of-Change on historical PRs whose outcome is known, and for scoring the results without
letting the answers leak into anything that writes probes.

Two files describe a benchmark:

- an **inputs** file (`id,repo,pr,pr_url,pr_title,...,main_sha_merge_first_parent,pr_side_sha_merge_commit,...`):
  safe to give to a probe generator together with the PR text and base-side code;
- an **answer key** (`id,label,ground_truth_links,what_broke,...`): ground truth. Only the scorer reads it.

## Answer-key firewall (`poc/leakage.py`)

`check_bundle(bundle, answers, base_files=..., pr_files=..., base_root=...)` refuses a prompt bundle (PR text plus
files) that contains any URL, issue or PR reference, or phrase from the answer key, or any file that exists only on
the PR side. The answer key is turned into SHA-256 fingerprints first; refusals never print the matched text.

```
python -m poc.leakage fingerprint <answer-key.csv> --out fingerprints.json   # hashes only, no plain text
python -m poc.leakage check bundle.json --fingerprints fingerprints.json     # exit 1 = refused
```

## Probe lint (`poc/probe_quality.py`)

`lint(src, changed_files)` rejects a probe that asserts (`assert`, `pytest.raises`), imports a network or process
module (`socket`, `subprocess`, ...), writes outside the temporary folder, or imports none of the modules the PR
changed. It parses the probe; it never imports or runs it.

## Scorer (`evals/score_bench.py`, standard library only)

Joins result files with the answer key on the case ID only. Reports regression recall, false-alarm rate,
abstention and precision with Wilson 95% intervals, and compares two baselines with an exact two-sided McNemar test
on the paired regression cases.

```
python -m evals.score_bench --answers <answer-key.csv> --results runs/bench-v0 --baseline full --vs tests
```

With 15 regressions, 5 flagged gives a 95% interval of 15.2% to 58.3%; 6 discordant cases against 0 gives p = 0.031.
Small benchmarks can only show large effects.
