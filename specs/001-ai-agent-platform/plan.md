# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]  
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]  
**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]  
**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]  
**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]
**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]  
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]  
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]  
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

[Gates determined based on constitution file]

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

# Implementation Plan: 2brain AI Agent Platform

**Branch**: `001-ai-agent-platform` | **Date**: 2026-03-14 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-ai-agent-platform/spec.md`

## Summary

A self-hosted AI agent platform for an engineering agency. Engineers define agents as LangGraph `StateGraph`s; client systems invoke them via a FastAPI service authenticated by `X-API-Key`. The platform runs entirely on Docker Compose (single host), uses LiteLLM as an LLM gateway with provider-alias routing, Redis for session memory and job queues, Qdrant + Mem0 for semantic memory, Langfuse for LLM tracing, and NeMo Guardrails for per-client policy enforcement. A single bootstrap script initialises every service and generates all internal secrets on a fresh Docker host.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: FastAPI, LangGraph, LiteLLM (gateway container), Pydantic v2, rq (Redis Queue), Mem0, Qdrant-client, NeMo Guardrails, structlog, Langfuse SDK (Python), Caddy (reverse proxy + TLS)  
**Storage**: PostgreSQL 16 (job records, agent definitions, client configs), Redis 7 (session memory TTL, rq job queue, policy cache), Qdrant (vector store for semantic memory)  
**Testing**: pytest + pytest-asyncio; LiteLLM calls mocked via `unittest.mock`; integration tests guarded by `TEST_INTEGRATION=true`  
**Target Platform**: Linux server running Docker Compose (single host); development on macOS via Docker Desktop using identical compose file  
**Project Type**: web-service (FastAPI API) + background worker (rq worker)  
**Performance Goals**: p95 synchronous invocation ≤ 30 s; batch job re-queue within 60 s of restart; policy config change propagation ≤ 30 s  
**Constraints**: Single-host only; no streaming in v1; no horizontal scaling; no managed cloud services as hard dependencies  
**Scale/Scope**: Multi-tenant via namespace isolation (`{client_id}:*`); concurrent capacity bounded by host resources only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### §I Architecture

| Principle | Status | Notes |
|-----------|--------|-------|
| Cloud agnostic first | ✅ PASS | All components run as Docker containers. PostgreSQL, Redis, Qdrant, Langfuse, LiteLLM are all self-hosted. No managed cloud service is a hard dependency. |
| Single compose file as source of truth | ✅ PASS | `docker-compose.yml` at repo root defines all services. Bootstrap runs `docker compose up`. |
| Explicit over implicit | ✅ PASS | All configuration via env vars; `.env.example` required to document every variable. |
| One service, one responsibility | ✅ PASS | agent-api (FastAPI), agent-worker (rq), litellm (gateway), langfuse-server, langfuse-worker, langfuse-db (Postgres), redis, qdrant, caddy — each container does one thing. |

### §II Code Quality

| Principle | Status | Notes |
|-----------|--------|-------|
| Python 3.12+ with modern typing | ✅ PASS | Enforced via pyproject.toml `requires-python = ">=3.12"`. |
| Pydantic for all data boundaries | ✅ PASS | All API request/response, all inter-service messages, all config objects use Pydantic models. |
| Async by default | ✅ PASS | FastAPI routes and all I/O are async. rq worker executes sync tasks in a thread pool via `asyncio.to_thread` where needed. |
| No business logic in route handlers | ✅ PASS | Route handlers call graph execution functions only. Logic lives in `agent/graphs/`. |
| Fail loudly on startup | ✅ PASS | Bootstrap and service startup validate all required env vars and dependency reachability before accepting traffic. |

### §III Testing Standards

| Principle | Status | Notes |
|-----------|--------|-------|
| Every agent graph has an offline unit test | ✅ PASS | Each `StateGraph` in `agent/graphs/` has a corresponding test in `tests/graphs/` with mocked LiteLLM. |
| Integration tests opt-in via `TEST_INTEGRATION=true` | ✅ PASS | Enforced by pytest marker. |
| Evals separate from tests | ✅ PASS | `evals/` directory, separate CI step. |
| Test file mirrors source file | ✅ PASS | Naming convention enforced. |

### §IV Observability Standards

| Principle | Status | Notes |
|-----------|--------|-------|
| Every agent execution produces a Langfuse trace | ✅ PASS | LangGraph callbacks instrument every graph run. LiteLLM emits callbacks automatically to Langfuse. |
| Structured logging everywhere | ✅ PASS | `structlog` with JSON renderer. `print()` banned in production code. |
| Health endpoints are honest | ✅ PASS | `GET /health` probes Redis, PostgreSQL, Qdrant. Returns 503 if any unreachable. |

### §V Security

| Principle | Status | Notes |
|-----------|--------|-------|
| Secrets never in code or logs | ✅ PASS | All secrets from env vars. Log sanitisation strips key-shaped values. |
| API authentication on every external endpoint | ✅ PASS | FastAPI dependency checks `X-API-Key` on every route except `/health`. |
| Tool sandboxing | ✅ PASS | Code-execution tool runs in isolated subprocess / E2B sandbox. |

### §VI LLM Interaction

| Principle | Status | Notes |
|-----------|--------|-------|
| Agents talk to LiteLLM, never providers directly | ✅ PASS | Agent code uses `openai.AsyncOpenAI(base_url=LITELLM_BASE_URL)`. No `anthropic` SDK imports in agent code. |
| Model names are always aliases | ✅ PASS | `default`, `fast`, `embedding` in agent code. LiteLLM config maps to provider strings. |
| Prompts are versioned assets | ✅ PASS | System prompts in `agent/prompts/*.md`, loaded at startup. Missing prompt causes startup failure. |

### §VII Extensibility

| Principle | Status | Notes |
|-----------|--------|-------|
| New agents follow LangGraph pattern | ✅ PASS | All agents in `agent/graphs/` as compiled `StateGraph`. |
| Tools are MCP-compatible | ✅ PASS | Tool definitions follow MCP schema. |
| Multi-tenancy via namespace | ✅ PASS | Redis: `{client_id}:session:{session_id}`, Qdrant: `{client_id}_memory`. |
| Infrastructure as code | ✅ PASS | `docker-compose.yml` is the IaC definition for all infrastructure. `infra/` holds bootstrap script and any supplemental IaC. |

**GATE RESULT: ✅ ALL PASS — proceeding to Phase 0**

## Project Structure

### Documentation (this feature)

```text
specs/001-ai-agent-platform/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── agent-api.yaml   # OpenAPI schema for agent-api
│   └── litellm-aliases.md  # Model alias contract
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
agent/                        # Python package: agent execution runtime
├── graphs/                   # LangGraph StateGraph definitions (one file per agent type)
│   ├── conversational.py     # Stateful conversational agent graph
│   ├── tool_agent.py         # Tool-calling agent graph (ReAct loop)
│   └── batch_agent.py        # Batch/pipeline agent graph
├── tools/                    # MCP-compatible tool implementations
│   ├── web_search.py
│   ├── code_exec.py          # Sandboxed code execution tool
│   ├── rest_caller.py
│   └── file_ops.py           # Sandboxed file operations tool
├── memory.py                 # Memory interface (Mem0 + Redis abstraction layer)
├── policy.py                 # NeMo Guardrails pre/post processing wrapper
├── prompts/                  # Versioned system prompt assets (.md files)
│   ├── conversational.md
│   ├── tool_agent.md
│   └── batch_agent.md
└── guardrails/               # Per-client NeMo Guardrails Colang configs
    └── {client_id}.co        # One file per client (loaded at startup)

api/                          # FastAPI application
├── main.py                   # App factory, startup validation, router registration
├── routes/
│   ├── agents.py             # POST /api/v1/run, POST /api/v1/jobs
│   ├── jobs.py               # GET /api/v1/jobs/{job_id}
│   ├── approvals.py          # POST /api/v1/approvals/{request_id}/decide
│   └── health.py             # GET /health
├── deps.py                   # FastAPI dependencies (auth, client ID resolution)
└── models/                   # Pydantic request/response models
    ├── run.py
    ├── jobs.py
    └── approvals.py

worker/                       # rq worker entrypoint
└── tasks.py                  # Job handler functions consumed by rq worker

infra/                        # Infrastructure as code
├── bootstrap.sh              # One-command bootstrap script
├── docker-compose.yml        # Single source of truth for all services
├── .env.example              # All env vars documented with safe defaults
├── caddy/
│   └── Caddyfile             # Reverse proxy + TLS config
└── litellm/
    └── config.yaml.template  # LiteLLM model alias config (envsubst at boot)

tests/
├── graphs/                   # Unit tests for every StateGraph (offline, mocked LLM)
│   ├── test_conversational.py
│   ├── test_tool_agent.py
│   └── test_batch_agent.py
├── routes/                   # Unit tests for API route handlers
├── integration/              # Integration tests (TEST_INTEGRATION=true)
└── conftest.py               # Fixtures, mock LiteLLM client factory

evals/                        # LLM quality evaluation (separate CI step)

pyproject.toml                # Project metadata, dependencies, pytest config
Makefile                      # Developer convenience targets
```

**Structure Decision**: Multi-package layout with `agent/` (execution runtime), `api/` (FastAPI layer), `worker/` (rq worker), and `infra/` (all IaC). The `agent/` package is the only place for business logic; `api/` routes delegate entirely to it. `infra/` contains the compose file as the single IaC source of truth.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — complexity tracking not required.
