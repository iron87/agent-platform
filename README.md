# 2brain Platform

Self-hosted multi-tenant AI agent platform for agencies and internal teams.

Architecture diagram: [docs/architecture.md](docs/architecture.md)  
Reconstructed ADRs: [docs/adrs.md](docs/adrs.md)

## Overview

2brain provides:

- API-based agent invocation (sync, session, async)
- strict tenant isolation per tenant
- tool-enabled agents with allowlists
- tracing and observability hooks
- policy and safety controls

## Quick Start

Prerequisites:

- Python 3.12+
- Docker + Docker Compose
- Make

```bash
python -m pip install -e '.[dev]'
cp infra/.env.example .env
bash infra/bootstrap.sh
```

Light mode (Mac-friendly):

```bash
bash infra/bootstrap-light.sh
```

## Capabilities

### Platform & Runtime

| Area | Capability | Status |
|------|------------|--------|
| Bootstrap | One-command startup, idempotent bootstrap | ✅ |
| Health | Dependency readiness probes | ✅ |
| Auth | X-API-Key tenant authentication | ✅ |
| Execution | Sync + session + async modes | ✅ |
| Queue | rq-based background execution | ✅ |
| Policies | Per-tenant policy hooks + redaction/blocking/injection detection | ✅ |
| HITL | Approval-gated tool execution + approval APIs (`GET/POST /approvals`) | ✅ |

### Tools

| Tool | Description | Status |
|------|-------------|--------|
| web_search | DuckDuckGo Instant Answer wrapper | ✅ |
| code_exec | Sandboxed Python execution | ✅ |
| rest_caller | HTTP caller with timeout handling | ✅ |
| file_ops | Sandboxed file operations | ✅ |
| tool registry | Per-agent allowlist resolution | ✅ |
| tool-agent loop | retries/fail handling in graph | ✅ |
| tool call spans | args/output/latency/error callbacks | ✅ |

### LLM, Memory, Observability

| Area | Capability | Status |
|------|------------|--------|
| LLM routing | Alias-based models (`default` / `fast` / `embedding`) + `default → fast` fallback | ✅ |
| Memory | Redis session + Qdrant semantic memory | ✅ |
| Tracing | Langfuse callback integration + fallback event hooks | ✅ |
| Replay | Trace replay workflow | ⏳ |

## LLM Routing & Fallback

LiteLLM is booted from `infra/litellm/config.yaml.template` (or `infra/litellm/config.light.yaml.template` in the lightweight stack). The file is rendered from the active `.env` values when the container starts, so alias changes stay configuration-only.

| Alias | Purpose | Runtime behavior |
|------|---------|------------------|
| `default` | primary reasoning/chat alias | retries the primary provider and automatically falls back to `fast` |
| `fast` | low-latency chat alias | used directly for lightweight tasks and as the `default` fallback |
| `embedding` | semantic-memory embedding alias | uses the configured embedding endpoint |

Operational notes:
- set `LOCAL_DEFAULT_MODEL`, `LOCAL_FAST_MODEL`, `LOCAL_EMBEDDING_MODEL`, and the matching `*_API_BASE` variables in `.env`
- tune `LITELLM_BUDGET_DEFAULT`, `LITELLM_BUDGET_FAST`, `LITELLM_BUDGET_EMBEDDING`, plus the tenant-wide defaults `LITELLM_TENANT_BUDGET_TOTAL` and `LITELLM_TENANT_BUDGET_DURATION` for virtual-key budgeting
- after changing alias or fallback wiring, restart the LiteLLM service (`bash infra/bootstrap-light.sh` is enough for local dev)
- `agent_definitions.model_alias` is validated at runtime and must stay within `default`, `fast`, or `embedding`; conversational, tool, and batch graphs all resolve through these aliases only

## Policy Enforcement (US8)

The policy runtime supports per-tenant enforcement with a fail-open strategy:

- redaction rules via regex (`policy.json` per tenant)
- blocked category detection (`credentials`, `pii`, `violence`, `hate`)
- prompt injection detection with optional blocking
- structured violation logs without raw sensitive values
- hot-reload by directory hash + policy version tracking

Example:
- policy walkthrough: [examples/us8_policy_example.py](examples/us8_policy_example.py)
- redaction-only walkthrough: [examples/us8_policy_redaction_only_example.py](examples/us8_policy_redaction_only_example.py)
- injection-block walkthrough: [examples/us8_policy_injection_block_example.py](examples/us8_policy_injection_block_example.py)
- hot-reload walkthrough: [examples/us8_policy_hot_reload_example.py](examples/us8_policy_hot_reload_example.py)

## Architecture & Agent Graphs

In 2brain, the **agent graph** is the runtime workflow that the platform executes after `AgentService` has loaded an `agent_definition`.
It is the piece that decides how the agent moves from input to output, not just which model is called.

| Graph type | File | Purpose |
|---|---|---|
| `conversational` | `agent/graphs/conversational.py` | sync and session chat |
| `tool_agent` | `agent/graphs/tool_agent.py` | multi-step tool use with allowlists |
| `batch_agent` | `agent/graphs/batch_agent.py` | async / backend-oriented job processing |

Useful references:
- detailed architecture view: [`docs/architecture.md`](docs/architecture.md)
- reconstructed implementation ADRs: [`docs/adrs.md`](docs/adrs.md)

## Tenant Registry (Agency / Tenant / Agent Census)

The runtime tenant entity is the tenant record in table tenants. In agency scenarios, each agency can own multiple tenant workspaces, and each tenant can have multiple agent definitions.

Current model in DB:

- agency: organizational concept (not a dedicated table yet)
- tenant: isolation boundary in table tenants
- agent: executable definition in table agent_definitions

### Schema summary

tenants

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| id | UUID | yes | PK, tenant identifier |
| name | TEXT | yes | human-readable tenant name |
| api_key_hash | TEXT | yes | unique; accepts bcrypt hash (recommended) |
| approval_endpoint | TEXT | no | webhook for approval flows |
| is_active | BOOLEAN | yes | active tenants are accepted by auth |
| created_at | TIMESTAMPTZ | yes | default now() |

agent_definitions

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| id | UUID | yes | PK, referenced by API payloads |
| name | TEXT | yes | unique agent name |
| model_alias | TEXT | yes | must be one of: default, fast, embedding |
| prompt_file | TEXT | yes | path to prompt file in repo |
| graph_type | TEXT | yes | conversational, tool_agent, or batch_agent |
| tools | TEXT[] | yes | allowed tool names for this agent |
| hitl_tools | TEXT[] | yes | subset of tools gated by approval |
| max_execution_seconds | INTEGER | yes | must be > 0 |
| semantic_memory_enabled | BOOLEAN | yes | semantic memory toggle |
| version | INTEGER | yes | definition version, must be > 0 |
| created_at / updated_at | TIMESTAMPTZ | yes | audit timestamps |

Validation note:

- auth checks only active tenants and compares X-API-Key against tenants.api_key_hash
- model_alias and graph_type are DB-constrained, invalid values fail at insert/update

### Fast path for local dev

```bash
bash examples/us2_seed_dev.sh
```

This seeds:

- one tenant in tenants
- one agent in agent_definitions

### Manual census (tenants and agents)

0. Open psql in the postgres container:

```bash
docker compose -f infra/docker-compose.yml --env-file .env exec -T postgres \
  sh -lc 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

1. Generate bcrypt hash for an API key (recommended):

```bash
python - <<'PY'
import bcrypt
api_key = "sk-your-tenant-key"
print(bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode())
PY
```

2. Insert tenant and agent:

```sql
INSERT INTO tenants (id, name, api_key_hash, approval_endpoint, is_active)
VALUES (
  '11111111-1111-1111-1111-111111111111',
  'Agency A / Team Alpha',
  '<bcrypt-hash>',
  NULL,
  TRUE
);

INSERT INTO agent_definitions (
  id, name, model_alias, prompt_file, graph_type, tools, hitl_tools,
  max_execution_seconds, semantic_memory_enabled, version
)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'support-triage',
  'default',
  'examples/prompts/us2_support_prompt.txt',
  'conversational',
  ARRAY['web_search','code_exec']::text[],
  ARRAY[]::text[],
  60,
  FALSE,
  1
);
```

Recommended idempotent version (upsert):

```sql
INSERT INTO tenants (id, name, api_key_hash, approval_endpoint, is_active)
VALUES (
  '11111111-1111-1111-1111-111111111111',
  'Agency A / Team Alpha',
  '<bcrypt-hash>',
  NULL,
  TRUE
)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  api_key_hash = EXCLUDED.api_key_hash,
  approval_endpoint = EXCLUDED.approval_endpoint,
  is_active = EXCLUDED.is_active;

INSERT INTO agent_definitions (
  id, name, model_alias, prompt_file, graph_type, tools, hitl_tools,
  max_execution_seconds, semantic_memory_enabled, version
)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'support-triage',
  'default',
  'examples/prompts/us2_support_prompt.txt',
  'conversational',
  ARRAY['web_search','code_exec']::text[],
  ARRAY[]::text[],
  60,
  FALSE,
  1
)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  model_alias = EXCLUDED.model_alias,
  prompt_file = EXCLUDED.prompt_file,
  graph_type = EXCLUDED.graph_type,
  tools = EXCLUDED.tools,
  hitl_tools = EXCLUDED.hitl_tools,
  max_execution_seconds = EXCLUDED.max_execution_seconds,
  semantic_memory_enabled = EXCLUDED.semantic_memory_enabled,
  version = EXCLUDED.version,
  updated_at = now();
```

3. Query census:

```sql
SELECT id, name, is_active FROM tenants ORDER BY created_at DESC;

SELECT id, name, graph_type, model_alias, tools
FROM agent_definitions
ORDER BY created_at DESC;
```

4. Minimal consistency checks:

```sql
SELECT id, name, is_active
FROM tenants
ORDER BY created_at DESC;

SELECT id, name, model_alias, graph_type, cardinality(tools) AS tools_count
FROM agent_definitions
ORDER BY created_at DESC;

SELECT count(*) AS jobs_total, count(DISTINCT tenant_id) AS tenants_seen
FROM jobs;
```

Agency-level census suggestion:

- until an agencies table exists, encode agency in tenants.name (for example Agency A / Team Alpha) or add an agency tag in a metadata convention managed by your provisioning scripts.

## Tenant CLI (`2brain`)

A React Ink/TypeScript CLI for interacting with the platform from the terminal.
Source: `packages/tenant-cli/`

### Install (local dev)

```bash
npm install
npm --workspace @2brain/tenant-cli run build
npm link --workspace @2brain/tenant-cli   # makes `2brain` available globally
```

Or without installing, pass `-- <args>` via the root workspace script:

```bash
npm run cli:dev -- --help
```

### Configure a profile

```bash
2brain config set \
  --base-url http://localhost:8000/api/v1 \
  --api-key sk-your-tenant-key

# Named profiles (e.g. staging, prod)
2brain config set --profile staging \
  --base-url https://staging.example.com/api/v1 \
  --api-key sk-staging-key

2brain config list
2brain config get --profile staging
2brain config delete staging
```

Profiles are stored at `~/.config/2brain/config.json`.  
`--base-url` and `--api-key` also read from `BRAIN_BASE_URL` / `BRAIN_API_KEY` env vars as fallback.

### Run an agent (sync)

```bash
2brain run --agent-id <uuid> --input "Ciao, chi sei?"

# with a specific profile
2brain run --agent-id <uuid> --input "test" --profile staging

# JSON output (useful for scripting)
2brain run --agent-id <uuid> --input "test" --json
```

### Session chat (interactive)

```bash
2brain session chat --agent-id <uuid> --session-id <session-uuid>
# Type /exit to quit
```

### Async jobs

```bash
# Submit and get job_id immediately
2brain jobs submit --agent-id <uuid> --input "Analizza il backlog"

# Check status
2brain jobs status --job-id <uuid>

# Submit and block until terminal state (default timeout 300s)
2brain jobs wait --job-id <uuid>
2brain jobs wait --job-id <uuid> --timeout 120 --json
```

### Human-in-the-loop approvals

```bash
# View a pending approval
2brain approvals get --approval-id <uuid>

# Approve
2brain approvals approve --approval-id <uuid> --reviewer-id ops@example.com

# Reject with reason
2brain approvals reject --approval-id <uuid> --reviewer-id ops@example.com \
  --reason "tool call out of scope"

# Legacy alias kept for compatibility
2brain approvals decide --approval-id <uuid> --reviewer-id ops@example.com --approve
```

### Global flags (all commands)

| Flag | Description |
|------|-------------|
| `--profile <name>` | Use a named stored profile (default: `default`) |
| `--base-url <url>` | Override API base URL for this invocation |
| `--api-key <key>` | Override API key for this invocation |
| `--json` | Output machine-readable JSON instead of text |

---

## API & Examples

- Examples index: [examples/README.md](examples/README.md)
- Sync invocation: [examples/us2_sync_example.py](examples/us2_sync_example.py)
- Session flow: [examples/us3_session_example.py](examples/us3_session_example.py)
- Async job flow: [examples/us5_async_job_example.py](examples/us5_async_job_example.py)
- Trace replay flow: [examples/us7_trace_replay_example.py](examples/us7_trace_replay_example.py)
- Policy enforcement flow: [examples/us8_policy_example.py](examples/us8_policy_example.py)
- Policy redaction-only flow: [examples/us8_policy_redaction_only_example.py](examples/us8_policy_redaction_only_example.py)
- Policy injection-block flow: [examples/us8_policy_injection_block_example.py](examples/us8_policy_injection_block_example.py)
- Policy hot-reload flow: [examples/us8_policy_hot_reload_example.py](examples/us8_policy_hot_reload_example.py)
- Approval API flow: [examples/us9_approval_flow_example.py](examples/us9_approval_flow_example.py)
- CLI end-to-end flow: [examples/us10_cli_end_to_end.sh](examples/us10_cli_end_to_end.sh)
- CLI sync flow: [examples/us10_cli_run_example.sh](examples/us10_cli_run_example.sh)
- CLI async jobs flow: [examples/us10_cli_jobs_example.sh](examples/us10_cli_jobs_example.sh)
- CLI approvals flow: [examples/us10_cli_approvals_example.sh](examples/us10_cli_approvals_example.sh)
- Tool flows:
  - [examples/us4_web_search_example.py](examples/us4_web_search_example.py)
  - [examples/us4_code_exec_example.py](examples/us4_code_exec_example.py)
  - [examples/us4_rest_caller_example.py](examples/us4_rest_caller_example.py)
  - [examples/us4_file_ops_example.py](examples/us4_file_ops_example.py)
  - [examples/us4_tool_agent_graph_example.py](examples/us4_tool_agent_graph_example.py)

### Async API quick reference

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{
    "agent_id": "00000000-0000-0000-0000-000000000001",
    "input": "Analyze the backlog and return a short triage summary"
  }'

curl -H "X-API-Key: $AGENT_API_KEY" \
  http://localhost:8000/api/v1/jobs/<job-id>
```

Status values: `pending`, `running`, `completed`, `failed`, `interrupted`.
On success, `GET /api/v1/jobs/{job_id}` returns the final `output` and `trace_id`.

## Roadmap

| Phase | Scope | Status |
|------|-------|--------|
| Phase 1 | Setup | ✅ |
| Phase 2 | Foundations | ✅ |
| Phase 3 | US1 Bootstrap | ✅ |
| Phase 4 | US2 Sync Invocation | ✅ |
| Phase 5 | US3 Conversational Sessions | ✅ |
| Phase 6 | US4 Tool-Using Agent (T044-T050) | ✅ |
| Phase 7 | US5 Async lifecycle completion (T051-T057) | ✅ |
| Phase 8 | US6 Provider routing/fallback hardening | ✅ |
| Phase 9 | US7 Trace review/replay | ✅ |
| Phase 10 | US8 Policy enforcement hardening | ✅ |
| Phase 11 | US9 HITL approvals | ✅ |
| Phase 12 | US10 Tenant CLI | ✅ |
| Phase 13 | Polish and cross-cutting tests/docs | ⏳ |

## Developer Section

### Test commands

```bash
make PYTHON=/path/to/python test-all
make PYTHON=/path/to/python test-integration
make PYTHON=/path/to/python test-full
```

### Runtime checks

```bash
docker compose -f infra/docker-compose.yml --env-file .env config
docker compose -f infra/docker-compose.yml --env-file .env ps
curl -i http://localhost:8000/health
```

### Repository structure

- agent/: runtime, graphs, tools, policy, memory
- api/: FastAPI app, routes, schemas, auth dependencies
- worker/: async queue integration
- infra/: bootstrap, compose, migrations, proxy, templates
- examples/: runnable scenarios
- tests/: unit and integration suites
- specs/: product specs, plan, tasks, contracts
