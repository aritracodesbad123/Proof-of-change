# Needs-attention notes for joint review (batch 0fa0016)

8 runs found a difference between main and the PR. None has outside proof either way.

## caronc/apprise #1783: tags= and tag= on urls not supported

- Verdict: Needs attention (Medium confidence)
- Claim (PR title): tags= and tag= on urls not supported
- What differed: 10 test(s) removed on the PR side; 274 test(s) ran on main, 274 on the PR; 10 new test(s) pass, 264 unchanged; rejected: claim pattern(s) C1 match none of this probe's observation names, so the probe is not counted
- Evidence: [PR](https://github.com/caronc/apprise/pull/1783) · [report](runs/apprise-1783/REPORT.md) · [record](runs/apprise-1783/record.json)
- **Flag:** tests removed on the PR side can be a deliberate cleanup; check before counting it as a problem.

## oyvindwe/connectlife-ha #742: Start WM26 G400 with program options, also from standby

- Verdict: Needs attention (Low confidence)
- Claim (PR title): Start WM26 G400 with program options, also from standby
- What differed: probe: 2 observation(s) need attention: C2.import_error does not differ although the claim says it does (C2); C3.import_error does not differ although the claim says it does (C3); probe model-probe1 has no measured line coverage (coverage produced no data (exit 0); see probe-coverage.log); it does not count as covering the change; probe model-probe2 has no measured line coverage (coverage produced no data (exit 0); see probe-coverage.log); it does not count as covering the change; tests: tests p
- Evidence: [PR](https://github.com/oyvindwe/connectlife-ha/pull/742) · [report](runs/connectlife-ha-742/REPORT.md) · [record](runs/connectlife-ha-742/record.json)
- **Flag:** the report's trust check marks this run untrustworthy (the run failed its own checks).

## bopen/elevation #89: Cache missing tiles

- Verdict: Needs attention (High confidence)
- Claim (PR title): Cache missing tiles
- What differed: probe: 3 observation(s) need attention: exception_type does not differ although the claim says it does (C1); spool_files_count does not differ although the claim says it does (C1); tile_cached_after_ensure does not differ although the claim says it does (C1); probe model-probe1 is not_adequate (no changed executable line exists on the main side (new files, comments or docstrings only), so the probe cannot be shown to reach the change); its matching results do not count; tests: 37 test(s) ran on 
- Evidence: [PR](https://github.com/bopen/elevation/pull/89) · [report](runs/elevation-89/REPORT.md) · [record](runs/elevation-89/record.json)

## Second-Hand-Friends/kleinanzeigen-bot #1361: feat: add manual browser login command

- Verdict: Needs attention (Medium confidence)
- Claim (PR title): feat: add manual browser login command
- What differed: 1 new test(s) fail on the PR; 322 test(s) ran on main, 335 on the PR; 12 new test(s) pass, 307 unchanged; 15 test failure(s) pre-existing and identical on both sides; probe: 1 observation(s) need attention: probe1.exit_code differs and no claim covers it; rejected: claim pattern(s) C1, C4 match none of this probe's observation names, so the probe is not counted; rejected: claim pattern(s) C2, C3, C4, C5 match none of this probe's observation names, so the probe is not counted
- Evidence: [PR](https://github.com/Second-Hand-Friends/kleinanzeigen-bot/pull/1361) · [report](runs/kleinanzeigen-bot-1361/REPORT.md) · [record](runs/kleinanzeigen-bot-1361/record.json)

## doobidoo/mcp-memory-service #1531: fix(maintenance): regenerate_embeddings writes vectors into their store partition

- Verdict: Needs attention (Low confidence)
- Claim (PR title): fix(maintenance): regenerate_embeddings writes vectors into their store partition
- What differed: 194 test(s) pass on main but fail on the PR; 7 other outcome change(s); 200 test(s) fail on main and pass on the PR; 4517 test(s) ran on main, 4517 on the PR; 2 new test(s) pass, 4072 unchanged (130 of them skipped on both sides); 176 test failure(s) pre-existing and identical on both sides; rejected: claim pattern(s) C1, C2 match none of this probe's observation names, so the probe is not counted; rejected: claim pattern(s) C2 match none of this probe's observation names, so the probe is not co
- Evidence: [PR](https://github.com/doobidoo/mcp-memory-service/pull/1531) · [report](runs/mcp-memory-service-1531/REPORT.md) · [record](runs/mcp-memory-service-1531/record.json)
- **Flag:** the report's trust check marks this run untrustworthy (the run failed its own checks).
- **Flag: possible environment issue.** 194 tests passed on main and failed on the PR, while 200 went the other way. Swings that large in both directions point to the test environment, not the change.

## doobidoo/mcp-memory-service #1603: fix(mcp): propagate tool exceptions so failures reach the client as isError (#1601)

- Verdict: Needs attention (Medium confidence)
- Claim (PR title): fix(mcp): propagate tool exceptions so failures reach the client as isError (#1601)
- What differed: probe: 4 observation(s) need attention: refused.exception_raised differs and no claim covers it; refused.first_element_text differs and no claim covers it; refused.first_element_type differs and no claim covers it; refused.return_type differs and no claim covers it; rejected: claim pattern(s) C1, C2, C3 match none of this probe's observation names, so the probe is not counted; tests: 29 test(s) ran on main, 35 on the PR; 6 new test(s) pass, 30 unchanged (1 of them skipped on both sides)
- Evidence: [PR](https://github.com/doobidoo/mcp-memory-service/pull/1603) · [report](runs/mcp-memory-service-1603/REPORT.md) · [record](runs/mcp-memory-service-1603/record.json)

## mlflow/mlflow #26542: Load latest Databricks scorers from the scheduled-scorers REST config so feedback records the scorer version

- Verdict: Needs attention (Medium confidence)
- Claim (PR title): Load latest Databricks scorers from the scheduled-scorers REST config so feedback records the scorer version
- What differed: 3 test(s) removed on the PR side; 1 test(s) re-parametrized (2 -> 1 ids); 64 test(s) ran on main, 65 on the PR; 6 new test(s) pass, 59 unchanged; probe model-c1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-c2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-c3
- Evidence: [PR](https://github.com/mlflow/mlflow/pull/26542) · [report](runs/mlflow-26542/REPORT.md) · [record](runs/mlflow-26542/record.json)
- **Flag:** tests removed on the PR side can be a deliberate cleanup; check before counting it as a problem.

## The-PR-Agent/pr-agent #4189: perf(similar_issue): batch embeddings before individual retries

- Verdict: Needs attention (Medium confidence)
- Claim (PR title): perf(similar_issue): batch embeddings before individual retries
- What differed: probe: 4 observation(s) need attention: tc2_call_count does not differ although the claim says it does (C2); tc2_outcome does not differ although the claim says it does (C2); tc4_call_count does not differ although the claim says it does (C2); tc4_outcome does not differ although the claim says it does (C2); probe: claim(s) C1, C2 proven; tests: 43 test(s) ran on main, 47 on the PR; 4 new test(s) pass, 43 unchanged
- Evidence: [PR](https://github.com/The-PR-Agent/pr-agent/pull/4189) · [report](runs/pr-agent-4189/REPORT.md) · [record](runs/pr-agent-4189/record.json)

