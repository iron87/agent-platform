# 2brain Platform

A self-hosted AI agent platform for engineering teams that build and operate AI agents for clients.

The project is cloud-agnostic and designed to run on a single Docker host, with API access, worker orchestration, model routing via LiteLLM aliases, and observability services.

Architecture diagram: [docs/architecture.md](docs/architecture.md)

## What This Project Is

2brain provides a foundation to:

- Define and run agents in a controlled runtime.
- Expose agent capabilities through stable HTTP APIs.
- Isolate client workloads in a multi-tenant architecture.
- Trace, inspect, and debug executions.

Current repository status: foundational runtime (Phases 1-2) and US1-US5 core workflows are implemented. Tools implementation (T044-T047) in progress.

## Features & Capabilities

### ✅ Implemented Features

**Core Platform**
- One-command bootstrap from fresh Docker host (`bash infra/bootstrap.sh`)
- Health probes for all dependencies (Postgres, Redis, Qdrant)
- TLS-terminated reverse proxy (Caddy)
- Structured JSON logging across all services

**API & Authentication**
- FastAPI service with X-API-Key authentication per client
- Multi-tenant isolation via namespace scoping
- Health endpoint (`GET /health`)

**Agent Execution**
- **Synchronous invocation** — `POST /api/v1/run` with immediate response
- **Conversational sessions** — per-session TTL-based memory and turn history
- **Async job submission** — long-running tasks with polling/status retrieval
- Session-aware execution with context preservation across turns
- Full trace propagation and correlation IDs

**LLM Integration**
- LiteLLM proxy for multi-provider routing (OpenAI, Anthropic, etc.)
- Alias-based model calls (`default`, `fast`, `embedding`)
- Automatic provider fallback on failure
- Budget tracking and rate limiting per alias

**Tools** (Agent Capabilities)
- ✅ **Web Search** — DuckDuckGo Instant Answer API (encyclopedia-style results)
- ✅ **Code Execution** — sandboxed Python subprocess with timeout + resource limits
- 🚧 **REST Caller** — HTTP requests with headers, auth, timeout handling (in progress)
- 🚧 **File Operations** — read/write files in isolated directory (in progress)
- Tool allowlist per agent definition

**Memory & Context**
- Redis-backed session store with automatic TTL refresh
- Semantic memory via Mem0 + Qdrant vector database
- Per-client memory isolation

**Observability**
- Langfuse v3 integration for LLM tracing
- Full trace tree: inputs, LLM calls, tool calls, outputs, latencies
- Trace ID correlation across requests
- Graceful degradation if observability unavailable

**Policy & Security**
- Per-client NeMo Guardrails enforcement (hot-reloadable, <30s propagation)
- Response redaction and content blocking
- Injection detection
- Secret isolation (env vars stripped from tool subprocess)

**Job Processing**
- Redis Queue (rq) for background job execution
- Retry policy with configurable intervals
- Job status tracking (pending, running, completed, failed)
- Postgres as authoritative job record store
- Graceful worker shutdown with SIGTERM

### 🚧 In Progress

- REST caller tool (T046)
- File operations tool (T047)
- Tool registry and agent-level tool allowlisting (T048)
- Tool-agent graph loop with retry/fallback (T049)
- Tool call observability integration (T050)
- Full async job lifecycle and status reconciliation (T051-T057)

### 📋 Planned (Future Phases)

- Multi-provider fallback routing optimization (US6)
- Trace replay capabilities (US7)
- Advanced policy enforcement (US8)
- HITL (Human-In-The-Loop) approval gates
- Horizontal scaling and multi-host orchestration

## Use Cases

Main use cases this platform targets:

- One-command bootstrap of a complete self-hosted AI stack on a fresh machine.
- Synchronous agent invocation from client systems.
- Conversational sessions with contextual memory.
- Tool-enabled agents for multi-step automation.
- Async batch processing with polling/retrieval.
- Provider-agnostic model routing and fallback.
- Trace review and replay for production diagnostics.
- Per-client policy enforcement (redaction/blocking/injection checks).
- Human-in-the-loop approvals for high-risk actions.

## Current Implementation Status

**Phase 1 (Setup)**: ✅ Complete
- T001-T008: Project scaffolding, Docker Compose stack, bootstrap automation, Caddy TLS

**Phase 2 (Foundations)**: ✅ Complete
- T009-T023: Config loader, logging, database schema, FastAPI app, LangGraph state, LiteLLM wrapper, Redis session store, Mem0 semantic memory, policy registry, Langfuse tracing, rq queue, agent service orchestrator

**Phase 3 (US1 — Bootstrap)**: ✅ Complete
- T024-T030: Health checks, bootstrap idempotency, startup summary, docker healthchecks, quickstart guide

**Phase 4 (US2 — Sync Invocation)**: ✅ Complete
- T031-T037: Run request/response schemas, sync route handler, agent definition lookup, trace propagation, route registration, auth enforcement

**Phase 5 (US3 — Conversational Sessions)**: ✅ Complete
- T038-T043: Session turn serialization, session history (load/append/TTL), conversational graph execution, session-aware service branching, session validation, tenant-isolated session keys

**Phase 6 (US4 — Tool-Using Agent)**: 🚧 In Progress
- ✅ T044: Web search tool wrapper (`agent/tools/web_search.py`)
- ✅ T045: Code execution tool wrapper (`agent/tools/code_exec.py`) — sandboxed subprocess, timeout, output capture
- ✅ T046: REST caller tool wrapper (`agent/tools/rest_caller.py`) — timeout handling, method allowlist, response truncation
- ⏳ T047: File operations tool wrapper (planned)
- ⏳ T048-T050: Tool registry, tool-agent graph loop, observability integration

**Phase 7 (US5 — Async Jobs)**: 🚧 In Progress
- ✅ T055: Async enqueue path with retry policy
- ⏳ T051-T057: Job schemas, handlers, repository CRUD, worker task runner, status reconciliation

## How To Use

### Runnable Examples

- Examples index: [examples/README.md](examples/README.md)
- **US2** (sync invocation): [examples/us2_sync_example.py](examples/us2_sync_example.py) + [examples/us2_seed_dev.sh](examples/us2_seed_dev.sh)
- **US3** (conversational sessions): [examples/us3_session_example.py](examples/us3_session_example.py)
- **US4** (tool-using agent):
  - Web search: [examples/us4_web_search_example.py](examples/us4_web_search_example.py) — mode 1 (tool-only) and mode 2 (with LLM loop)
  - Code execution: [examples/us4_code_exec_example.py](examples/us4_code_exec_example.py) — mode 1 (tool-only) and mode 2 (with LLM loop)
  - REST caller: [examples/us4_rest_caller_example.py](examples/us4_rest_caller_example.py) — mode 1 (tool-only) and mode 2 (with LLM loop)

### Prerequisites

- Python 3.12+
- Docker + Docker Compose
- Make

### 1) Install local development dependencies

```bash
python -m pip install -e '.[dev]'
```

### 2) Prepare environment

```bash
cp infra/.env.example .env
```

Local-first strategy (recommended for development):

- Configure local endpoint and model aliases:
- `LOCAL_LLM_API_BASE`
- `LOCAL_DEFAULT_MODEL`
- `LOCAL_FAST_MODEL`
- `LOCAL_EMBEDDING_MODEL`
- `LOCAL_EMBEDDING_API_BASE`

Cloud strategy:

- Customize `infra/litellm/config.yaml.template` to cloud providers.
- Set provider keys (`ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY`).

### 3) Bootstrap stack

```bash
bash infra/bootstrap.sh
```

Lightweight mode (recommended on Mac laptops):

```bash
bash infra/bootstrap-light.sh
```

This starts only `postgres`, `redis`, `litellm`, and `agent-api`.

### 4) Useful development commands

```bash
make PYTHON=/path/to/python test-all
make PYTHON=/path/to/python test-integration
make PYTHON=/path/to/python test-full
make PYTHON=/path/to/python run-api
make PYTHON=/path/to/python run-worker
make bootstrap
make bootstrap-light
docker compose -f infra/docker-compose.yml --env-file .env config
docker compose -f infra/docker-compose.light.yml --env-file .env config
```

## How To Test

### A) Code quality and unit-level checks

```bash
make PYTHON=/path/to/python test-all
```

This runs:

- pytest (default suite)
- ruff
- mypy

### B) Integration suite (opt-in)

```bash
make PYTHON=/path/to/python test-integration
```

`test-integration` is opt-in and may be skipped when the runtime stack is not up.

### C) Full local pipeline

```bash
make PYTHON=/path/to/python test-full
```

### D) Runtime stack verification (up and running)

1. Validate compose rendering:

```bash
docker compose -f infra/docker-compose.yml --env-file .env config
```

2. Start stack:

```bash
bash infra/bootstrap.sh
```

Or start lightweight stack:

```bash
bash infra/bootstrap-light.sh
```

3. Check service status:

```bash
docker compose -f infra/docker-compose.yml --env-file .env ps
docker compose -f infra/docker-compose.light.yml --env-file .env ps
```

4. Probe core dependencies:

```bash
curl -f http://localhost:6333/healthz
curl -f http://localhost:4000/health/liveliness
curl -f http://localhost:8000/live
curl -i http://localhost:8000/health
curl -I http://localhost:3000
```

Notes:
- `/live` is liveness (process up) and is used by Docker healthcheck.
- `/health` is readiness (postgres/redis/qdrant probes) and can return 503 when dependencies are degraded.

### E) Focused artifact checks

```bash
python -c "import agent, api, worker; print('ok')"
python -c "from pathlib import Path; print((Path('infra/.env.example').exists(), Path('infra/litellm/config.yaml.template').exists()))"
python -c "from pathlib import Path; print((Path('infra/docker-compose.yml').exists(), Path('infra/bootstrap.sh').exists(), Path('infra/caddy/Caddyfile').exists()))"
```

## Notes On Current Scope

- Phase 1 is complete and validated with automated checks.
- Runtime API and business endpoints are implemented in later phases.

## Documentation Maintenance Rule

This README is a living document. After each implemented task in specs/001-ai-agent-platform/tasks.md, it must be updated with:

1. What was implemented.
2. How to use it.
3. How to verify it with tests or commands.

## Repository Structure

- agent/: agent runtime and orchestration.
- api/: FastAPI application.
- worker/: worker and async jobs.
- infra/: bootstrap and infrastructure configuration.
- tests/: unit and integration tests.
- specs/: specification, plan, and task documents.
