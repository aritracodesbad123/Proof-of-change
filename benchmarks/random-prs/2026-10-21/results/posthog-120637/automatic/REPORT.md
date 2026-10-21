# Reviewer report: PostHog/posthog#120637: fix(aio): warn only on slow thread waits in on_asyncify_pool

Run `posthog-120637`, tested 2026-10-21 19:41 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `5492834eef22efd122549356c73d26b3d0ae040a`. Report generated 2026-10-21 19:43 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** fix(aio): warn only on slow thread waits in on_asyncify_pool ([PostHog/posthog#120637](https://github.com/PostHog/posthog/pull/120637)).
- **What we observed:** install failed (1); see setup-main.log.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

Verdict: could_not_verify. install failed (1); see setup-main.log

Model summary is advisory; the code verdict above is authoritative.

### Agent swarm (advisory)

| Role | Model | Status | Notes |
|---|---|---|---|
| judge | nvidia/Nemotron-3-Ultra-550b-a55b | ok | - |
| helper | nvidia/Nemotron-3_5-Lightning | ok | install failure: check setup-main.log for details; aio thread wait warning pattern observed; baseline full with no probe summary data |
| summary | nvidia/nemotron-3-super-120b-a12b | ok | model returned empty text; filled from code verdict/reason |

judge/helper/summary are advisory; code owns the verdict

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 5.7 GB (of 15.6 GB).
- Setup check: free disk 97.9 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 7 results
- Query: posthog python setup install instructions https://github.com/PostHog/posthog site:github.com/PostHog/posthog
- Query: posthog python documentation install https://github.com/PostHog/posthog site:github.com/PostHog/posthog
- Query: posthog python install requirements https://pypi.org/project/posthog/ https://github.com/PostHog/posthog site:pypi.org
- Source: posthog · PyPI — https://pypi.org/project/posthog/
- Source: posthog-async · PyPI — https://pypi.org/project/posthog-async/
- Source: GitHub - PostHog/posthog-demo-3000 · GitHub — https://github.com/PostHog/posthog-demo-3000
- Source: GitHub - PostHog/posthog-python: Send usage data from your Python code to PostHog. · GitHub — https://github.com/PostHog/posthog-python
- Source: posthog/Dockerfile.sandbox at master · PostHog/posthog · GitHub — https://github.com/PostHog/posthog/blob/master/Dockerfile.sandbox
- Source: posthog-live · Releases · PostHog/posthog · GitHub — https://github.com/PostHog/posthog/releases?q=posthog-live&amp%3Bexpanded=true
- Source: posthog-live · Releases · PostHog/posthog · GitHub — https://github.com/PostHog/posthog/releases?q=posthog-live&expanded=true
- Setup plan: the same packages on main and pr.
- Setup plan: aioboto3 is noted, installed with the project.
- Setup plan: aiohttp is noted, installed with the project.
- Setup plan: aiokafka is noted, installed with the project.
- Setup plan: anthropic is noted, installed with the project.
- Setup plan: asyncstdlib is noted, installed with the project.
- Setup plan: beautifulsoup4 is noted, installed with the project.
- Setup plan: boto3 is noted, installed with the project.
- Setup plan: brotli is noted, installed with the project.
- Setup plan: celery is noted, installed with the project.
- Setup plan: celery-redbeat is noted, installed with the project.
- Setup plan: certifi is noted, installed with the project.
- Setup plan: clickhouse-connect is noted, installed with the project.
- Setup plan: clickhouse-driver is noted, installed with the project.
- Setup plan: clickhouse-pool is noted, installed with the project.
- Setup plan: circular-dict is noted, installed with the project.
- Setup plan: cryptography is noted, installed with the project.
- Setup plan: PyNaCl is noted, installed with the project.
- Setup plan: dagster is noted, installed with the project.
- Setup plan: dagster-cloud is noted, installed with the project.
- Setup plan: dagster-aws is noted, installed with the project.
- Setup plan: dagster-celery is noted, installed with the project.
- Setup plan: dagster-docker is noted, installed with the project.
- Setup plan: dagster-k8s is noted, installed with the project.
- Setup plan: dagster-pipes is noted, installed with the project.
- Setup plan: dagster-postgres is noted, installed with the project.
- Setup plan: dagster-slack is noted, installed with the project.
- Setup plan: dagster-webserver is noted, installed with the project.
- Setup plan: deltalake is noted, installed with the project.
- Setup plan: dj-database-url is noted, installed with the project.
- Setup plan: django is noted, installed with the project.
- Setup plan: django-axes is noted, installed with the project.
- Setup plan: django-cors-headers is noted, installed with the project.
- Setup plan: django-extensions is noted, installed with the project.
- Setup plan: django-filter is noted, installed with the project.
- Setup plan: django-loginas is noted, installed with the project.
- Setup plan: django-prometheus is noted, installed with the project.
- Setup plan: django-redis is noted, installed with the project.
- Setup plan: django-structlog is noted, installed with the project.
- Setup plan: django-two-factor-auth is noted, installed with the project.
- Setup plan: djangorestframework is noted, installed with the project.
- Setup plan: djangorestframework-csv is noted, installed with the project.
- Setup plan: djangorestframework-dataclasses is noted, installed with the project.
- Setup plan: dlt is noted, installed with the project.
- Setup plan: dnspython is noted, installed with the project.
- Setup plan: drf-exceptions-hog is noted, installed with the project.
- Setup plan: drf-extensions is noted, installed with the project.
- Setup plan: drf-spectacular is noted, installed with the project.
- Setup plan: drf-spectacular-sidecar is noted, installed with the project.
- Setup plan: geoip2 is noted, installed with the project.
- Setup plan: google-ads is noted, installed with the project.
- Setup plan: google-cloud-bigquery is noted, installed with the project.
- Setup plan: google-cloud-bigquery-storage is noted, installed with the project.
- Setup plan: google-cloud-iam is noted, installed with the project.
- Setup plan: google-genai is noted, installed with the project.
- Setup plan: granian is noted, installed with the project.
- Setup plan: grimp is noted, installed with the project.
- Setup plan: grpcio is noted, installed with the project.
- Setup plan: gspread is noted, installed with the project.
- Setup plan: hogql-parser is noted, installed with the project.
- Setup plan: hogql-parser-rs is noted, installed with the project.
- Setup plan: humanize is noted, installed with the project.
- Setup plan: infi-clickhouse-orm is noted, installed with the project.
- Setup plan: ipython is noted, installed with the project.
- Setup plan: jsonref is noted, installed with the project.
- Setup plan: kafka-python is noted, installed with the project.
- Setup plan: kombu is noted, installed with the project.
- Setup plan: jsonpatch is noted, installed with the project.
- Setup plan: langchain is noted, installed with the project.
- Setup plan: langchain-community is noted, installed with the project.
- Setup plan: langchain-core is noted, installed with the project.
- Setup plan: langchain-openai is noted, installed with the project.
- Setup plan: langchain-anthropic is noted, installed with the project.
- Setup plan: langgraph is noted, installed with the project.
- Setup plan: langgraph-checkpoint is noted, installed with the project.
- Setup plan: lxml is noted, installed with the project.
- Setup plan: lzstring is noted, installed with the project.
- Setup plan: markdown-it-py is noted, installed with the project.
- Setup plan: mcp is noted, installed with the project.
- Setup plan: mimesis is noted, installed with the project.
- Setup plan: mistralai is noted, installed with the project.
- Setup plan: more-itertools is noted, installed with the project.
- Setup plan: nanoid is noted, installed with the project.
- Setup plan: natsort is noted, installed with the project.
- Setup plan: nh3 is noted, installed with the project.
- Setup plan: numpy is noted, installed with the project.
- Setup plan: openai is noted, installed with the project.
- Setup plan: openpyxl is noted, installed with the project.
- Setup plan: orjson is noted, installed with the project.
- Setup plan: ormsgpack is noted, installed with the project.
- Setup plan: pandas is noted, installed with the project.
- Setup plan: paramiko is noted, installed with the project.
- Setup plan: pillow is noted, installed with the project.
- Setup plan: protobuf is noted, installed with the project.
- Setup plan: posthoganalytics is noted, installed with the project.
- Setup plan: polars is noted, installed with the project.
- Setup plan: psycopg2-binary is noted, installed with the project.
- Setup plan: psycopg is noted, installed with the project.
- Setup plan: pyarrow is noted, installed with the project.
- Setup plan: pydantic is noted, installed with the project.
- Setup plan: pypdf is noted, installed with the project.
- Setup plan: pyod is noted, installed with the project.
- Setup plan: pyjwt is noted, installed with the project.
- Setup plan: pymssql is noted, installed with the project.
- Setup plan: pymysql is noted, installed with the project.
- Setup plan: pymongo is noted, installed with the project.
- Setup plan: pyroscope-io is noted, installed with the project.
- Setup plan: croniter is noted, installed with the project.
- Setup plan: python-dateutil is noted, installed with the project.
- Setup plan: python-docx is noted, installed with the project.
- Setup plan: python-snappy is noted, installed with the project.
- Setup plan: python3-saml is noted, installed with the project.
- Setup plan: pytz is noted, installed with the project.
- Setup plan: rapidfuzz is noted, installed with the project.
- Setup plan: redis is noted, installed with the project.
- Setup plan: requests is noted, installed with the project.
- Setup plan: retry is noted, installed with the project.
- Setup plan: s3fs is noted, installed with the project.
- Setup plan: scikit-learn is noted, installed with the project.
- Setup plan: scipy is noted, installed with the project.
- Setup plan: semantic-version is noted, installed with the project.
- Setup plan: simple-salesforce is noted, installed with the project.
- Setup plan: slack-sdk is noted, installed with the project.
- Setup plan: snowflake-connector-python is noted, installed with the project.
- Setup plan: social-auth-app-django is noted, installed with the project.
- Setup plan: social-auth-core is noted, installed with the project.
- Setup plan: django-scim2 is noted, installed with the project.
- Setup plan: sqlparse is noted, installed with the project.
- Setup plan: sshtunnel is noted, installed with the project.
- Setup plan: statshog is noted, installed with the project.
- Setup plan: stripe is noted, installed with the project.
- Setup plan: structlog is noted, installed with the project.
- Setup plan: temporalio is noted, installed with the project.
- Setup plan: tenacity is noted, installed with the project.
- Setup plan: tiktoken is noted, installed with the project.
- Setup plan: tldextract is noted, installed with the project.
- Setup plan: trafilatura is noted, installed with the project.
- Setup plan: trino is noted, installed with the project.
- Setup plan: types-cachetools is noted, installed with the project.
- Setup plan: css-inline is noted, installed with the project.
- Setup plan: click is noted, installed with the project.
- Setup plan: owners-yaml is noted, installed with the project.
- Setup plan: personhog-proto is noted, installed with the project.
- Setup plan: umap-learn is noted, installed with the project.
- Setup plan: tbb is noted, installed with the project.
- Setup plan: whitenoise is noted, installed with the project.
- Setup plan: xgboost is noted, installed with the project.
- Setup plan: onnxruntime is noted, installed with the project.
- Setup plan: xmlsec is noted, installed with the project.
- Setup plan: zstd is noted, installed with the project.
- Setup plan: zxcvbn is noted, installed with the project.
- Setup plan: pyyaml is noted, installed with the project.
- Setup plan: chdb is noted, installed with the project.
- Setup plan: elevenlabs is noted, installed with the project.
- Setup plan: django-oauth-toolkit is noted, installed with the project.
- Setup plan: azure-ai-projects is noted, installed with the project.
- Setup plan: azure-ai-inference is noted, installed with the project.
- Setup plan: azure-storage-blob is noted, installed with the project.
- Setup plan: opentelemetry-sdk is noted, installed with the project.
- Setup plan: opentelemetry-instrumentation-aiokafka is noted, installed with the project.
- Setup plan: opentelemetry-instrumentation-aiohttp-client is noted, installed with the project.
- Setup plan: opentelemetry-instrumentation-asgi is noted, installed with the project.
- Setup plan: opentelemetry-instrumentation-celery is noted, installed with the project.
- Setup plan: opentelemetry-instrumentation-django is noted, installed with the project.
- Setup plan: opentelemetry-instrumentation-kafka-python is noted, installed with the project.
- Setup plan: opentelemetry-instrumentation-psycopg is noted, installed with the project.
- Setup plan: opentelemetry-instrumentation-redis is noted, installed with the project.
- Setup plan: opentelemetry-instrumentation-requests is noted, installed with the project.
- Setup plan: opentelemetry-exporter-otlp-proto-grpc is noted, installed with the project.
- Setup plan: asgiref is noted, installed with the project.
- Setup plan: user-agents is noted, installed with the project.
- Setup plan: django-admin-inline-paginator is noted, installed with the project.
- Setup plan: fastavro is noted, installed with the project.
- Setup plan: pydantic-avro is noted, installed with the project.
- Setup plan: playwright is noted, installed with the project.
- Setup plan: linkedin-api-client is noted, installed with the project.
- Setup plan: glom is noted, installed with the project.
- Setup plan: modal is noted, installed with the project.
- Setup plan: databricks-sql-connector is noted, installed with the project.
- Setup plan: databricks-sdk is noted, installed with the project.
- Setup plan: free-email-domains is noted, installed with the project.
- Setup plan: disposable-email-domains is noted, installed with the project.
- Setup plan: pymediainfo is noted, installed with the project.
- Setup plan: cachetools is noted, installed with the project.
- Setup plan: gitpython is noted, installed with the project.
- Setup plan: duckdb is noted, installed with the project.
- Setup plan: bingads is noted, installed with the project.
- Setup plan: markdown-to-mrkdwn is noted, installed with the project.
- Setup plan: webauthn is noted, installed with the project.
- Setup plan: botocore is noted, installed with the project.
- Setup plan: defusedxml is noted, installed with the project.
- Setup plan: confluent-kafka is noted, installed with the project.
- Setup plan: blake3 is noted, installed with the project.
- Setup plan: pixelhog is noted, installed with the project.
- Setup plan: google-re2 is noted, installed with the project.
- Setup plan: scrubadub is noted, installed with the project.
- Setup plan: braintrust-core is noted, installed with the project.
- Setup plan: wrapt is noted, installed with the project.
- Setup plan: limits is noted, installed with the project.
- Setup plan: deltalite is noted, installed with the project.
- Setup plan: posthog-hogland is noted, installed with the project.
- Setup plan: requests-oauthlib is noted, installed with the project.
- Setup plan: Python 3.14: not applied: python3.14 is not available to the local sandbox
- rerun, setup problem: main install failed after 3 tries.
- Demo helper: setup failure already labelled; the probe was not rerun.

### Background (related public bug reports, not used for the verdict)

1. "Slow response times · Issue #2680 · PostHog/posthog · GitHub"
   https://github.com/PostHog/posthog/issues/2680
   "## How to reproduce 1. Run posthog in with docker-compose 2. Place posthog under reasonably high load ## Environment PostHog cloud or self-managed? self-managed PostHog version/commit - 1.18.0 (via docker hub's latest tag) ## Additional con..."
2. "Product Analytics troubleshooting - Docs - PostHog"
   https://posthog.com/docs/product-analytics/troubleshooting
   "CIkbGliX3ZlcnNpb24iOiIxLjUzLjQiLCIkaW5zZXJ0X2lkIjoicnNsdm9pYXlocjEydXRvbSIsIiR0aW1lIjoxNjkxNDk2MjcxLjc5NywiZGlzdGluY3RfaWQiOiIxODlkNTA4YjBmNDRkNzAtMDBmN2E5MmRkNmE0MzgtMWE1MjU2MzQtMTNjNjgwLTE4OWQ1MDhiMGY1NTJlZSIsIiRkZXZpY2VfaWQiOiIxODlkMTM4Z..."
3. "Error Tracking – Catch and fix issues faster with PostHog"
   https://posthog.com/error-tracking
   "Connect error tracking with experimentation platform ✓ ✓ ## Que...

## Claims vs reality

No tests ran, so no claim could be checked.

## What changed in behavior

Not measured: install failed (1); see setup-main.log.

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

No probes ran: this record predates probes.

## Was the changed code exercised?

**Coverage: NOT MEASURED, record predates the coverage gate.** No coverage run exists for this record; nothing below is a measurement.

Coverage gate (python, confidence lower): coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result).

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `6de521c38ae9` of the PR against main (source-pair route).
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Run did not finish | ⚪ **COULD NOT VERIFY** | install failed (1); see setup-main.log | Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly. |
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result) | Not a measurement: this record is older than the coverage gate. Re-run the PR with the current ops/daily_run.py to measure it. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result) |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | ⚪ **SKIP** | no log lines to cite (no tests ran) |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run-folder>/report/posthog-120637 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/PostHog/posthog/pull/120637
```

## Evidence links

- [Pull request PostHog/posthog#120637](https://github.com/PostHog/posthog/pull/120637)
- [record.json](../../ops/runs/2026-10-21-check-1941/posthog-120637/record.json)
- [pr.diff](../../ops/runs/2026-10-21-check-1941/posthog-120637/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-21-check-1941/posthog-120637/setup-main.log)
- [git.log](../../ops/runs/2026-10-21-check-1941/posthog-120637/git.log)

## Glossary

| Term | Meaning |
|---|---|
| main | The library as it is today, without the PR. |
| PR | Pull request: a proposed change to the library. |
| run | One full pass of the selected tests. We do 3 per side, alternating main and PR. |
| flaky | A test that gives different results when nothing changed; it is ignored as evidence. |
| log line | A line in a pytest-*.log file: the raw output the verdict is based on. |
| route | How the two sides were built: nightly+patch, source-build or source-pair (see docs/OPERATIONS.md). |
| changed lines covered | How many of the PR's changed, executable Python lines ran during the PR side's tests. |
| re-parametrized | A test whose parameter ids changed (renamed cases); the new ids are judged on their own. |
