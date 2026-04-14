# 2brain Platform

Build and run production-ready AI agents with strict tenant isolation, tool governance, and full observability.

2brain is a self-hosted multi-tenant platform for agencies and internal teams that need to move from demos to dependable AI operations.

## Why 2brain

Most agent stacks are easy to demo and hard to operate.
2brain is designed for real deployment constraints:

- multi-tenant isolation by design
- policy and safety controls on every run
- human approvals for sensitive tool calls
- async execution for long tasks
- traceability and replay for debugging and audit

If your team needs to run many agents for many customers without losing control, this is what 2brain is built for.

## What You Can Do

- Invoke agents via API in sync, session, or async mode
- Run tool-enabled agents with explicit allowlists
- Apply per-tenant safety policies (redaction, blocking, injection checks)
- Gate risky tool actions behind human approvals
- Route across LLM aliases with managed fallback
- Track execution with observability hooks and tracing

## Product Surfaces

### 1) API Runtime

FastAPI backend with tenant-scoped auth, graph-based execution, policies, memory, and jobs.

### 2) Web Console

Visual operator interface for profile management, health, agent runs/replay, session chat, jobs polling, and approvals.

Run from repository root:

```bash
npm install
npm run web:dev
```

Open: http://localhost:5174

References:
- [packages/web-console/README.md](packages/web-console/README.md)
- [specs/002-web-console/quickstart.md](specs/002-web-console/quickstart.md)

Security posture for v1:
- Network-scoped operator access (no per-user login)
- `proxy` mode preferred in production (backend handles credentials)
- `direct` mode available for local/dev with profile API key

### 3) Tenant CLI (`2brain`)

Terminal workflow for operators and automation.

Source: `packages/tenant-cli/`

Install locally:

```bash
npm install
npm --workspace @2brain/tenant-cli run build
npm link --workspace @2brain/tenant-cli
```

Quick usage:

```bash
2brain config set --base-url http://localhost:8000/api/v1 --api-key sk-your-tenant-key
2brain run --agent-id <uuid> --input "Ciao, chi sei?"
2brain jobs submit --agent-id <uuid> --input "Analizza il backlog"
2brain approvals get --approval-id <uuid>
```

## Architecture at a Glance

Architecture diagram: [docs/architecture.md](docs/architecture.md)

Agent execution graphs:

| Graph type | File | Purpose |
|---|---|---|
| `conversational` | `agent/graphs/conversational.py` | sync and session chat |
| `tool_agent` | `agent/graphs/tool_agent.py` | multi-step tool use with allowlists |
| `batch_agent` | `agent/graphs/batch_agent.py` | async/background job processing |

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

Light Mode:

```bash
bash infra/bootstrap-light.sh
```

Health check:

```bash
curl -i http://localhost:8000/health
```

## Core Capabilities

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
| LLM routing | Alias-based models (`default` / `fast` / `embedding`) + `default -> fast` fallback | ✅ |
| Memory | Redis session + Qdrant semantic memory | ✅ |
| Tracing | Langfuse callback integration + fallback event hooks | ✅ |
| Replay | Trace replay workflow | ⏳ |

## LLM Routing and Fallback

LiteLLM is booted from:

- `infra/litellm/config.yaml.template` (full stack)
- `infra/litellm/config.light.yaml.template` (light stack)

Templates are rendered from active `.env` values at container startup.

| Alias | Purpose | Runtime behavior |
|------|---------|------------------|
| `default` | Primary reasoning/chat alias | Retries primary provider, then falls back to `fast` |
| `fast` | Low-latency chat alias | Used for lightweight tasks and as `default` fallback |
| `embedding` | Semantic memory embeddings | Uses configured embedding endpoint |

Operational notes:

- Set `LOCAL_DEFAULT_MODEL`, `LOCAL_FAST_MODEL`, `LOCAL_EMBEDDING_MODEL`, and related `*_API_BASE` vars in `.env`
- Tune budgets with `LITELLM_BUDGET_DEFAULT`, `LITELLM_BUDGET_FAST`, `LITELLM_BUDGET_EMBEDDING`
- Configure tenant-wide budget defaults with `LITELLM_TENANT_BUDGET_TOTAL` and `LITELLM_TENANT_BUDGET_DURATION`
- Restart LiteLLM after alias/fallback changes (for local dev, `bash infra/bootstrap-light.sh` is sufficient)
- `agent_definitions.model_alias` is runtime-validated and must be one of `default`, `fast`, `embedding`

## Policy Enforcement

Per-tenant policy runtime with fail-open strategy supports:

- regex redaction rules (`policy.json` per tenant)
- blocked category detection (`credentials`, `pii`, `violence`, `hate`)
- prompt injection detection with optional blocking
- structured violation logs without raw sensitive values
- hot reload via directory hash and version tracking

Walkthroughs:

- [examples/us8_policy_example.py](examples/us8_policy_example.py)
- [examples/us8_policy_redaction_only_example.py](examples/us8_policy_redaction_only_example.py)
- [examples/us8_policy_injection_block_example.py](examples/us8_policy_injection_block_example.py)
- [examples/us8_policy_hot_reload_example.py](examples/us8_policy_hot_reload_example.py)

## Tenant Model and Local Seeding

Current data model:

- agency: organizational concept (not a dedicated table yet)
- tenant: isolation boundary in `tenants`
- agent: executable definition in `agent_definitions`

Fast local seed:

```bash
bash examples/us2_seed_dev.sh
```

This seeds one tenant and one agent definition.

## API and Example Flows

Examples index: [examples/README.md](examples/README.md)

End-to-end examples:

- Sync invocation: [examples/us2_sync_example.py](examples/us2_sync_example.py)
- Session flow: [examples/us3_session_example.py](examples/us3_session_example.py)
- Async job flow: [examples/us5_async_job_example.py](examples/us5_async_job_example.py)
- Trace replay flow: [examples/us7_trace_replay_example.py](examples/us7_trace_replay_example.py)
- Approval API flow: [examples/us9_approval_flow_example.py](examples/us9_approval_flow_example.py)

CLI examples:

- [examples/us10_cli_end_to_end.sh](examples/us10_cli_end_to_end.sh)
- [examples/us10_cli_run_example.sh](examples/us10_cli_run_example.sh)
- [examples/us10_cli_jobs_example.sh](examples/us10_cli_jobs_example.sh)
- [examples/us10_cli_approvals_example.sh](examples/us10_cli_approvals_example.sh)

Tool examples:

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
On success, `GET /api/v1/jobs/{job_id}` returns final `output` and `trace_id`.

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

Test commands:

```bash
make PYTHON=/path/to/python test-all
make PYTHON=/path/to/python test-integration
make PYTHON=/path/to/python test-full
```

Runtime checks:

```bash
docker compose -f infra/docker-compose.yml --env-file .env config
docker compose -f infra/docker-compose.yml --env-file .env ps
curl -i http://localhost:8000/health
```

Repository structure:

- `agent/`: runtime, graphs, tools, policy, memory
- `api/`: FastAPI app, routes, schemas, auth dependencies
- `worker/`: async queue integration
- `infra/`: bootstrap, compose, migrations, proxy, templates
- `examples/`: runnable scenarios
- `tests/`: unit and integration suites
- `specs/`: product specs, plan, tasks, contracts
