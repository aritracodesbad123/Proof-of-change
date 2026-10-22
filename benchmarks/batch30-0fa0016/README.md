# 30-PR random batch, code version 0fa0016

Results of 30 random merged PRs checked on Proof-of-Change commit `0fa0016` (22 Oct 2026). Each run's record, report (Markdown and HTML) is in `runs/<repo>-<pr>/`.

- [Scoring](SCORING.md)
- [Needs-attention notes](NEEDS_ATTENTION_NOTES.md)
- `drawn.json`: the seed and the PRs drawn
- `labels.json`: what the GitHub search for outside proof found

## Results

| # | Repo | PR | Verdict | Confidence | Reason (one line) | Report |
|---|---|---|---|---|---|---|
| 1 | macs3-project/MACS | [#780](https://github.com/macs3-project/MACS/pull/780) | Could not verify | Low | install failed (1); see setup-main.log | [report](runs/MACS-780/REPORT.md) |
| 2 | macs3-project/MACS | [#784](https://github.com/macs3-project/MACS/pull/784) | Could not verify | Low | install failed (1); see setup-main.log | [report](runs/MACS-784/REPORT.md) |
| 3 | agentscope-ai/ReMe | [#627](https://github.com/agentscope-ai/ReMe/pull/627) | Could not verify | Low | not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; docstring-only change (AST equal after blanking docst… | [report](runs/ReMe-627/REPORT.md) |
| 4 | caronc/apprise | [#1783](https://github.com/caronc/apprise/pull/1783) | Needs attention | Medium | 10 test(s) removed on the PR side; 274 test(s) ran on main, 274 on the PR; 10 new test(s) pass, 264 unchanged; rejected: claim pattern(s) C1 match none of this … | [report](runs/apprise-1783/REPORT.md) |
| 5 | oyvindwe/connectlife-ha | [#742](https://github.com/oyvindwe/connectlife-ha/pull/742) | Could not verify | Low | the run failed its own checks: 3 alternating runs per side | [report](runs/connectlife-ha-742/REPORT.md) |
| 6 | home-assistant/core | [#187420](https://github.com/home-assistant/core/pull/187420) | Could not verify | Low | install failed (2); see setup-main.log | [report](runs/core-187420/REPORT.md) |
| 7 | home-assistant/core | [#187475](https://github.com/home-assistant/core/pull/187475) | Could not verify | Low | install failed (2); see setup-main.log | [report](runs/core-187475/REPORT.md) |
| 8 | home-assistant/core | [#187588](https://github.com/home-assistant/core/pull/187588) | Could not verify | Low | install failed (2); see setup-main.log | [report](runs/core-187588/REPORT.md) |
| 9 | bopen/elevation | [#89](https://github.com/bopen/elevation/pull/89) | Needs attention | High | probe: 3 observation(s) need attention: exception_type does not differ although the claim says it does (C1); spool_files_count does not differ although the clai… | [report](runs/elevation-89/REPORT.md) |
| 10 | frappe/erpnext | [#60004](https://github.com/frappe/erpnext/pull/60004) | Could not verify | Low | install failed (2); see setup-main.log | [report](runs/erpnext-60004/REPORT.md) |
| 11 | frappe/erpnext | [#61257](https://github.com/frappe/erpnext/pull/61257) | Could not verify | Low | install failed (2); see setup-main.log | [report](runs/erpnext-61257/REPORT.md) |
| 12 | googlefonts/glyphsLib | [#1208](https://github.com/googlefonts/glyphsLib/pull/1208) | Could not verify | Low | could not verify: claim(s) C1 expect a difference but no observation matches (docstring-only change (AST equal after blanking docstrings); behaviour claims hold… | [report](runs/glyphsLib-1208/REPORT.md) |
| 13 | Second-Hand-Friends/kleinanzeigen-bot | [#1361](https://github.com/Second-Hand-Friends/kleinanzeigen-bot/pull/1361) | Needs attention | Medium | 1 new test(s) fail on the PR; 322 test(s) ran on main, 335 on the PR; 12 new test(s) pass, 307 unchanged; 15 test failure(s) pre-existing and identical on both … | [report](runs/kleinanzeigen-bot-1361/REPORT.md) |
| 14 | doobidoo/mcp-memory-service | [#1531](https://github.com/doobidoo/mcp-memory-service/pull/1531) | Could not verify | Low | the run failed its own checks: pytest exit codes explained | [report](runs/mcp-memory-service-1531/REPORT.md) |
| 15 | doobidoo/mcp-memory-service | [#1603](https://github.com/doobidoo/mcp-memory-service/pull/1603) | Needs attention | Medium | probe: 4 observation(s) need attention: refused.exception_raised differs and no claim covers it; refused.first_element_text differs and no claim covers it; refu… | [report](runs/mcp-memory-service-1603/REPORT.md) |
| 16 | mlflow/mlflow | [#26542](https://github.com/mlflow/mlflow/pull/26542) | Needs attention | Medium | 3 test(s) removed on the PR side; 1 test(s) re-parametrized (2 -> 1 ids); 64 test(s) ran on main, 65 on the PR; 6 new test(s) pass, 59 unchanged; probe model-c1… | [report](runs/mlflow-26542/REPORT.md) |
| 17 | optiland/optiland | [#962](https://github.com/optiland/optiland/pull/962) | Could not verify | Low | could not verify: setup gap setup | [report](runs/optiland-962/REPORT.md) |
| 18 | optiland/optiland | [#963](https://github.com/optiland/optiland/pull/963) | Could not verify | Low | could not verify: setup gap setup | [report](runs/optiland-963/REPORT.md) |
| 19 | optuna/optuna | [#6873](https://github.com/optuna/optuna/pull/6873) | Could not verify | Low | not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; docstring-only change (AST equal after blanking docst… | [report](runs/optuna-6873/REPORT.md) |
| 20 | oceanbase/powercontext | [#1908](https://github.com/oceanbase/powercontext/pull/1908) | Could not verify | Low | tests produced no results on one side (collection failed; see pytest logs); probe model-probe-c1 is not_adequate (the probe crashed or printed no parsed output … | [report](runs/powercontext-1908/REPORT.md) |
| 21 | The-PR-Agent/pr-agent | [#4181](https://github.com/The-PR-Agent/pr-agent/pull/4181) | Could not verify | Low | no test actually ran on either side: 0 tests ran; 0 new test(s) pass, 0 unchanged; 1 test module(s) fail to load on both sides (tests.unittest.test_github_actio… | [report](runs/pr-agent-4181/REPORT.md) |
| 22 | The-PR-Agent/pr-agent | [#4183](https://github.com/The-PR-Agent/pr-agent/pull/4183) | Could not verify | Low | could not verify: setup gap setup | [report](runs/pr-agent-4183/REPORT.md) |
| 23 | The-PR-Agent/pr-agent | [#4189](https://github.com/The-PR-Agent/pr-agent/pull/4189) | Needs attention | Medium | probe: 4 observation(s) need attention: tc2_call_count does not differ although the claim says it does (C2); tc2_outcome does not differ although the claim says… | [report](runs/pr-agent-4189/REPORT.md) |
| 24 | pyrevitlabs/pyRevit | [#3743](https://github.com/pyrevitlabs/pyRevit/pull/3743) | Could not verify | Low | install failed (1); see setup-main.log | [report](runs/pyRevit-3743/REPORT.md) |
| 25 | dapr/python-sdk | [#1192](https://github.com/dapr/python-sdk/pull/1192) | Could not verify | Low | not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 9 test(s) ran on main, 10 on the PR; 1 new test(s) pa… | [report](runs/python-sdk-1192/REPORT.md) |
| 26 | tornadoweb/tornado | [#3787](https://github.com/tornadoweb/tornado/pull/3787) | Could not verify | Low | install failed (1); see setup-main.log | [report](runs/tornado-3787/REPORT.md) |
| 27 | basetenlabs/truss | [#2682](https://github.com/basetenlabs/truss/pull/2682) | Could not verify | Low | tests produced no results on one side (collection failed; see pytest logs); probe model-p1 is not_adequate (the probe crashed or printed no parsed output on eve… | [report](runs/truss-2682/REPORT.md) |
| 28 | vllm-project/vllm | [#58715](https://github.com/vllm-project/vllm/pull/58715) | Could not verify | Low | install failed (2); see setup-main.log | [report](runs/vllm-58715/REPORT.md) |
| 29 | vllm-project/vllm | [#59627](https://github.com/vllm-project/vllm/pull/59627) | Could not verify | Low | install failed (2); see setup-main.log | [report](runs/vllm-59627/REPORT.md) |
| 30 | vllm-project/vllm | [#60468](https://github.com/vllm-project/vllm/pull/60468) | Could not verify | Low | install failed (2); see setup-main.log | [report](runs/vllm-60468/REPORT.md) |
