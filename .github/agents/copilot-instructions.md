# 2brain-platform Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-01

## Active Technologies
- Python 3.12+ for backend and automation-friendly CLI commands; TypeScript + Node.js 22 for the optional React Ink TUI + FastAPI, Pydantic, httpx, structlog, existing SQLAlchemy/Redis/RQ stack; Typer + Rich for Python CLI ergonomics; React + Ink for interactive terminal flows (001-ai-agent-platform)
- PostgreSQL, Redis, Qdrant, Langfuse; CLI itself remains stateless except for a local profile/config file (001-ai-agent-platform)

- (001-ai-agent-platform)

## Project Structure

```text
src/
tests/
# 2brain-platform — GitHub Copilot Instructions

Auto-generated from feature plan `001-ai-agent-platform`. Last updated: 2026-04-01.

## Active Feature

**001-ai-agent-platform** — self-hosted AI agent platform for an engineering agency.
Plan: `specs/001-ai-agent-platform/plan.md`
Spec: `specs/001-ai-agent-platform/spec.md`
Branch: `001-ai-agent-platform`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 (`requires-python = ">=3.12"`) |
| API framework | FastAPI + Pydantic v2 |
| Agent runtime | LangGraph (`StateGraph`, `AsyncPostgresSaver` for HITL checkpoints) |
| LLM gateway | LiteLLM self-hosted proxy — use aliases `default` / `fast` / `embedding` only |
| Async jobs | rq (Redis Queue) + dedicated worker container |
| Session memory | Redis 7 — key pattern `{client_id}:session:{session_id}:*` (TTL 24 h) |
| Semantic memory | Mem0 Python library + Qdrant — per-client collection `{client_id}_memory` |
| Observability | Langfuse v3 self-hosted (requires ClickHouse + MinIO + Postgres + Redis) |
| Policy | NeMo Guardrails SDK — per-client Colang files at `agent/guardrails/{client_id}/` |
| Structured logging | `structlog` + JSON renderer — `print()` is banned |
| Reverse proxy | Caddy (automatic TLS via Let's Encrypt) |
| Database | PostgreSQL 16 |
| Testing | pytest + pytest-asyncio; integration tests guarded by `TEST_INTEGRATION=true` |
| Infrastructure | Single `docker-compose.yml` — no managed cloud services as hard dependencies |

---

## Project Structure

```text
agent/
├── graphs/          # LangGraph StateGraph implementations (conversational, tool_agent, batch_agent)
├── tools/           # Tool functions (web_search, code_exec, rest_caller, file_ops)
├── prompts/         # Versioned markdown prompt files
├── guardrails/      # Per-client NeMo Guardrails config dirs ({client_id}/)
├── memory.py        # SemanticMemoryStore protocol + Mem0/Qdrant implementation
└── policy.py        # Per-client LLMRails registry + hot-reload loop
api/
├── main.py          # FastAPI app factory
├── routes/          # Route modules — no business logic here
├── deps.py          # Shared FastAPI dependencies (auth, DB session)
└── models/          # Pydantic request/response models
worker/
└── tasks.py         # rq task definitions
infra/
├── docker-compose.yml
├── bootstrap.sh
├── .env.example
├── caddy/
└── litellm/         # config.yaml.template (envsubst at bootstrap)
tests/
├── graphs/          # Unit tests for each StateGraph (LiteLLM mocked)
├── routes/          # FastAPI route tests
├── integration/     # Integration tests (TEST_INTEGRATION=true)
└── conftest.py
evals/               # LLM evaluation scripts (separate from pytest)
pyproject.toml
Makefile
```

---

## Critical Conventions

1. **Agents use LiteLLM aliases exclusively** — never import `anthropic`, `openai`, or any provider SDK directly in agent code. Use `AsyncOpenAI(base_url=LITELLM_BASE_URL, api_key=LITELLM_API_KEY)` with `model="default"` / `"fast"` / `"embedding"`.
2. **No business logic in route handlers** — routes call `agent/` package functions only.
3. **All config from env vars** — no hardcoded connection strings or secrets.
4. **Pydantic for every data boundary** — API I/O, inter-service messages, config objects.
5. **Fail loudly on startup** — validate env vars and dependency reachability before accepting traffic.
6. **Structured logs only** — use `structlog.get_logger()`, never `print()` or `logging.basicConfig()`.
7. **Namespace isolation** — every Redis key, Qdrant collection, and LangGraph thread_id is prefixed with `{client_id}`.
8. **HITL interrupt pattern** — use `interrupt()` in graph nodes; resume with `Command(resume=value, update={...})` via the same `thread_id`.
9. **Async by default** — all I/O is `async`; sync code in rq tasks uses `asyncio.to_thread` where needed.

---

## Common Commands

```bash
# Start all services
docker compose up -d

# Unit tests (no running stack required)
docker compose run --rm agent-api pytest tests/ -v

# Integration tests
TEST_INTEGRATION=true docker compose run --rm agent-api pytest tests/integration/ -v

# Tail agent API logs
docker compose logs -f agent-api

# Bootstrap from scratch (generates secrets, starts all services)
bash infra/bootstrap.sh

# Health check
curl http://localhost:8000/health
```

---

## Key Design Decisions (Phase 0 Research Findings)

- **LangGraph HITL**: `interrupt(value)` raises `GraphInterrupt`; resume with `graph.ainvoke(Command(resume=value), config)` using the same `thread_id`. Node re-runs from its beginning on resume — side effects must be idempotent or placed after the `interrupt()` call.
- **Langfuse v3** requires **ClickHouse** and **MinIO** in addition to Postgres+Redis. These are included in `docker-compose.yml`.
- **Mem0 + Qdrant**: `Memory` is initialised per-client, pointing at collection `{client_id}_memory`. The LLM and embedder in Mem0 config must point to LiteLLM (`openai_base_url = LITELLM_BASE_URL/v1`).
- **NeMo Guardrails**: polled every 20 s for hot-reload. `None` return from `get_rails(client_id)` means no policy — graph is called directly without guardrails overhead.
- **rq**: not exactly-once. Use `Retry(max=3)`. PostgreSQL is the source of truth; rq is the executor. AOF Redis persistence required.
- **LiteLLM OTEL callback**: `callbacks: ["langfuse_otel"]` in `litellm/config.yaml` — do NOT use the legacy `langfuse` callback.

---

## Spec & Plan Artifacts

| Artifact | Path |
|----------|------|
| Spec | `specs/001-ai-agent-platform/spec.md` |
| Plan | `specs/001-ai-agent-platform/plan.md` |
| Research | `specs/001-ai-agent-platform/research.md` |
| Data model | `specs/001-ai-agent-platform/data-model.md` |
| OpenAPI contract | `specs/001-ai-agent-platform/contracts/agent-api.yaml` |
| Model alias contract | `specs/001-ai-agent-platform/contracts/litellm-aliases.md` |
| Quickstart | `specs/001-ai-agent-platform/quickstart.md` |

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

## Recent Changes
- 001-ai-agent-platform: Added Python 3.12+ for backend and automation-friendly CLI commands; TypeScript + Node.js 22 for the optional React Ink TUI + FastAPI, Pydantic, httpx, structlog, existing SQLAlchemy/Redis/RQ stack; Typer + Rich for Python CLI ergonomics; React + Ink for interactive terminal flows
