# 2brain Platform

Self-hosted multi-tenant AI agent platform for agencies and internal teams.

Architecture diagram: [docs/architecture.md](docs/architecture.md)

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
| Policies | Per-tenant policy hooks | ✅ (core) |
| HITL | Approval-gated tool execution | ⏳ |

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
- after changing alias or fallback wiring, restart the LiteLLM service (`bash infra/bootstrap-light.sh` is enough for local dev)
- `agent_definitions.model_alias` is validated at runtime and must stay within `default`, `fast`, or `embedding`

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

## API & Examples

- Examples index: [examples/README.md](examples/README.md)
- Sync invocation: [examples/us2_sync_example.py](examples/us2_sync_example.py)
- Session flow: [examples/us3_session_example.py](examples/us3_session_example.py)
- Async job flow: [examples/us5_async_job_example.py](examples/us5_async_job_example.py)
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
| Phase 8 | US6 Provider routing/fallback hardening | ⏳ |
| Phase 9 | US7 Trace review/replay | ⏳ |
| Phase 10 | US8 Policy enforcement hardening | ⏳ |
| Phase 11 | US9 HITL approvals | ⏳ |
| Phase 12 | Polish and cross-cutting tests/docs | ⏳ |

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
