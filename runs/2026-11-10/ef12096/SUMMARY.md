# Proof-of-Change go/no-go: 2026-11-10 on ef12096

2 report(s) in this folder: 1 need attention, 0 could not be verified, 1 verified. Built from every record.json stored in this folder, so a later one-PR run cannot narrow it.

## Needs a decision first

- **NEEDS ATTENTION**: encode/httpx#3766: Fix base_url query parameters corrupted during URL merging. 13 test(s) pass on every base run but fail on some pull-request runs: tests.client.test_async_client::test_100_continue[asyncio], tests.client.test_async_client::test_delete[asyncio], tests.client.test_async_client::test_patch[asyncio], tests.client.test_async_client::test_put[asyncio], tests.client.test_client::test_base_url (+8); 11 test(s) stable on the base and unstable only on the pull request, too mixed to call a regression: tests.client.test_async_client::test_head[asyncio], tests.client.test_client::test_build_post_request, tests.client.test_client::test_build_request, tests.client.test_client::test_get, tests.client.test_client::test_get_invalid_url[no-host] (+6); 1 test(s) fail on main and pass on the PR; 167 test(s) ran on main, 167 on the PR; 0 new test(s) pass, 125 unchanged (1 of them skipped on both sides); 18 test failure(s) pre-existing and identical on both sides

## All reports

| Verdict | Subject | Why | Report |
|---|---|---|---|
| NEEDS ATTENTION | encode/httpx#3766: Fix base_url query parameters corrupted during URL merging | 13 test(s) pass on every base run but fail on some pull-request runs: tests.client.test_async_client::test_100_continue[asyncio], tests.client.test_async_client::test_delete[asyncio], tests.client.test_async_client::test_patch[asyncio], tests.client.test_async_client::test_put[asyncio], tests.client.test_client::test_base_url (+8); 11 test(s) stable on the base and unstable only on the pull request, too mixed to call a regression: tests.client.test_async_client::test_head[asyncio], tests.client.test_client::test_build_post_request, tests.client.test_client::test_build_request, tests.client.test_client::test_get, tests.client.test_client::test_get_invalid_url[no-host] (+6); 1 test(s) fail on main and pass on the PR; 167 test(s) ran on main, 167 on the PR; 0 new test(s) pass, 125 unchanged (1 of them skipped on both sides); 18 test failure(s) pre-existing and identical on both sides | [PDF](httpx-3766/REPORT.pdf) |
| VERIFIED | mahmoud/boltons#740: strutils.strip_ansi: strip OSC sequences (fixes #739) | 52 test(s) fail on main and pass on the PR; 98 test(s) ran on main, 101 on the PR; 3 new test(s) pass, 46 unchanged; probe: claim(s) C1, C2, C3, C4, C5 proven | [PDF](boltons-740/REPORT.pdf) |
