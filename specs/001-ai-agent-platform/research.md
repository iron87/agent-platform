# Research: 2brain AI Agent Platform

**Phase**: 0 | **Date**: 2026-03-14 | **Plan**: [plan.md](plan.md)

All `NEEDS CLARIFICATION` items from the Technical Context are resolved here.

---

## 1. LangGraph HITL (interrupt mechanism)

**Decision**: Use `interrupt()` / `Command(resume=...)` with `AsyncPostgresSaver` checkpointer.

**Rationale**: `AsyncPostgresSaver` is the durable, production-recommended checkpointer for LangGraph HITL. It persists full graph state to PostgreSQL — the store we already operate — so no new infrastructure is required. The Redis checkpointer (`langgraph-checkpoint-redis`) is an option but adds a dependency on Redis key durability for long-lived approval windows; Postgres is safer.

**Alternatives considered**:
- `InMemorySaver` — dev only; state lost on restart.
- `AsyncRedisSaver` — viable, but HITL pauses can last hours/days; Redis eviction risk.
- `AsyncSqliteSaver` — single-process only; not container-safe.

**Key patterns**:

```python
# In a LangGraph node that needs approval
from langgraph.types import interrupt, Command

def tool_node(state: AgentState) -> AgentState:
    if tool_requires_approval(state["pending_tool"]):
        decision = interrupt({
            "tool_name": state["pending_tool"],
            "proposed_args": state["tool_args"],
            "job_id": state["job_id"],
        })
        if not decision["approved"]:
            return {"status": "rejected", "error": decision.get("reason")}
    return execute_tool(state)

# Resume from caller side
from langgraph.types import Command
await graph.ainvoke(Command(resume={"approved": True}), config={"configurable": {"thread_id": job_id}})
```

**Checkpointer wiring**:
```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
    await checkpointer.setup()     # creates tables if needed
    graph = build_graph().compile(checkpointer=checkpointer)
```

**App-level job status machine**:
`pending` → `running` → `interrupted` (awaiting approval) → `running` (resumed) → `completed` | `failed`

**Graph architecture decision**: Three **separate** compiled `StateGraph`s (conversational, tool-agent, batch) sharing the same checkpointer. Separate graphs give cleaner state schemas, independent observability, and distinct SLA handling. A parent router in `graphs/__init__.py` selects the graph by request type.

**Important constraint**: On resume, LangGraph re-executes the interrupted node from its beginning — nodes must be idempotent or all side-effects placed after the `interrupt()` call.

---

## 2. NeMo Guardrails — per-tenant config loading and hot-reload

**Decision**: Pre-load per-tenant `LLMRails` instances at startup; refresh via background polling every 20 s using mtime/hash comparison; atomic swap of the `rails_registry` dict.

**Rationale**: NeMo Guardrails has no built-in hot-reload for production (only a dev watchdog). A polling loop with atomic swap meets the ≤30 s propagation requirement (FR-028) without process restart. `RailsConfig.from_path(dir)` loads a tenant config directory; `RailsConfig.from_content(...)` loads a single `.co` + `.yaml` pair.

**Alternatives considered**:
- SIGHUP-triggered reload — fragile in Docker; requires signal plumbing.
- Guardrails server mode — adds another network hop and process; overkill.
- Restart on config change — violates FR-028.

**Key patterns**:

```python
# agent/policy.py
import asyncio, hashlib, threading
from pathlib import Path
from nemoguardrails import RailsConfig, LLMRails

_registry: dict[str, LLMRails] = {}
_registry_lock = threading.Lock()

def _build_rails(tenant_id: str, guardrails_dir: Path) -> LLMRails | None:
    cfg_dir = guardrails_dir / tenant_id
    if cfg_dir.is_dir():
        return LLMRails(RailsConfig.from_path(str(cfg_dir)))
    return None

def _refresh_loop(guardrails_dir: Path, interval: int = 20):
    while True:
        for cfg_dir in guardrails_dir.iterdir():
            tenant_id = cfg_dir.name
            rails = _build_rails(tenant_id, guardrails_dir)
            if rails:
                with _registry_lock:
                    _registry[tenant_id] = rails
        time.sleep(interval)

def get_rails(tenant_id: str) -> LLMRails | None:
    with _registry_lock:
        return _registry.get(tenant_id)     # None = no policy = pass-through (FR-030)
```

**Zero-overhead pass-through** (FR-030):
```python
rails = get_rails(request.tenant_id)
if rails is None:
    result = await graph.ainvoke(payload, config)     # no guardrails overhead
else:
    result = await rails_wrapped_invoke(rails, graph, payload, config)
```

---

## 3. Mem0 + Qdrant — namespacing and interface

**Decision**: One Qdrant collection per tenant (`{tenant_id}_memory`). One `Memory` instance per tenant, re-created lazily and cached. All embedding and LLM calls go through LiteLLM at `http://litellm:4000`.

**Rationale**: Per-collection isolation eliminates cross-tenant blast radius from `delete_all()`. Mem0 Python library only (no Mem0 server). The `SemanticMemoryStore` protocol in `agent/memory.py` is the swap boundary.

**Alternatives considered**:
- Shared collection + metadata filtering — simpler ops, but `delete_all()` safety issue is critical in multi-tenant.
- Custom Qdrant-direct module — more control, but Mem0 handles chunking, extraction, deduplication; worth keeping as default.

**Mem0 config per tenant**:
```python
def _mem0_config(tenant_id: str) -> dict:
    return {
        "llm": {
            "provider": "openai",
            "config": {
                "model": "default",
                "api_key": settings.LITELLM_API_KEY,
                "openai_base_url": settings.LITELLM_BASE_URL + "/v1",
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "embedding",
                "api_key": settings.LITELLM_API_KEY,
                "openai_base_url": settings.LITELLM_BASE_URL + "/v1",
                "embedding_dims": 1536,
            },
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": f"{tenant_id}_memory",
                "host": settings.QDRANT_HOST,
                "port": settings.QDRANT_PORT,
            },
        },
    }
```

**`agent/memory.py` protocol** (full interface in data-model.md):
```python
class SemanticMemoryStore(Protocol):
    async def upsert_fact(self, *, scope: MemoryScope, text: str, ...) -> str: ...
    async def search(self, *, scope: MemoryScope, query: str, limit: int) -> list[MemoryRecord]: ...
    async def delete(self, *, scope: MemoryScope, memory_id: str) -> None: ...
```

---

## 4. rq + Redis — job durability on restart

**Decision**: rq with retry (`Retry(max=3)`), PostgreSQL as authoritative job record store, Redis with AOF persistence, graceful SIGTERM shutdown for workers (`stop_grace_period: 30s` in compose).

**Rationale**: rq does not guarantee zero-loss on worker crash. With AOF Redis, queued (not-yet-started) jobs survive. Running jobs are re-queued after TTL expiry (default 420 s). With PG as source of truth, the platform can always reconcile. For FR-006 (survive restart within 60 s), the combination of retry + graceful stop + 420 s TTL meets the SLO.

**Alternatives considered**:
- Temporal — planned upgrade path (see plan §Upgrade Paths). For v1 scope, rq is sufficient.
- Celery — more complex; rq is simpler and sufficient for single-queue single-worker design.

**Key patterns**:
```python
from rq import Queue, Retry
from redis import Redis

q = Queue("agent_jobs", connection=Redis.from_url(settings.REDIS_URL),
          default_timeout=settings.JOB_TIMEOUT_SECONDS)

job = q.enqueue(
    "worker.tasks.run_agent_job",
    job_payload,
    job_id=str(job_record.id),
    retry=Retry(max=3, interval=[30, 120, 300]),
    result_ttl=86400,
    failure_ttl=7 * 86400,
    meta={"tenant_id": job_record.tenant_id},
)
```

**PG ↔ rq status bridge**: on_success/on_failure callbacks update the `jobs` table. A reconciliation loop runs every 60 s to mark jobs as `failed` if rq status is `failed` and PG still shows `running`.

---

## 5. LiteLLM proxy — alias config and Langfuse integration

**Decision**: Self-hosted LiteLLM via `ghcr.io/berriai/litellm:<pinned-version>`. Aliases in `litellm/config.yaml.template` (envsubst at bootstrap). Langfuse integration via OTEL callback (`langfuse_otel`).

**Rationale**: Pinned version tag (not `latest`) for reproducible upgrades. OTEL callback is the v3-aligned integration path with Langfuse. `config.yaml.template` + `envsubst` keeps secrets out of the committed file.

**Annotated `litellm/config.yaml.template`**:
```yaml
model_list:
  - model_name: default
    litellm_params:
      model: anthropic/claude-sonnet-4-5
      api_key: os.environ/ANTHROPIC_API_KEY
      max_budget: 300.0
      budget_duration: 30d

  - model_name: fast
    litellm_params:
      model: openai/gpt-4o-mini
      api_key: os.environ/OPENAI_API_KEY
      max_budget: 500.0
      budget_duration: 30d

  - model_name: embedding
    litellm_params:
      model: openai/text-embedding-3-small
      api_base: ${LOCAL_EMBEDDING_API_BASE}
      api_key: ${LOCAL_EMBEDDING_API_KEY}

litellm_settings:
  num_retries: 2
  request_timeout: 30
  fallbacks:
    - default: ["fast"]
  callbacks: ["langfuse_otel"]

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

**Agent SDK usage**:
```python
from openai import AsyncOpenAI

llm = AsyncOpenAI(
    base_url=settings.LITELLM_BASE_URL + "/v1",
    api_key=settings.LITELLM_API_KEY,
)
response = await llm.chat.completions.create(model="default", messages=...)
```

---

## 6. Langfuse v3 self-hosted — services and integration

**Decision**: Self-hosted Langfuse v3 via official Docker images. Use Langfuse `CallbackHandler` for LangGraph, OTEL callback from LiteLLM. MinIO for blob storage. `CallbackHandler` from `langfuse.langchain`.

**Critical infrastructure impact**: Langfuse v3 requires **ClickHouse** and **MinIO** (S3-compatible blob store) in addition to Postgres and Redis. These are **four additional containers** beyond what was originally specified. This is a mandatory infrastructure addition — Langfuse v3 does not support Postgres-only storage.

**Alternatives considered**:
- Langfuse v2 (Postgres only) — deprecated; no active support.
- OpenTelemetry + Jaeger — lacks the LLM-specific trace UI needed for FR-023.
- Keep Langfuse v3 with MinIO and ClickHouse — accepted. Both containers have small resource footprints at single-host scale.

**Trace pattern**:
```python
from langfuse.langchain import CallbackHandler

langfuse_handler = CallbackHandler(
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST,
)

result = await graph.ainvoke(
    payload,
    config={"callbacks": [langfuse_handler], "configurable": {"thread_id": job_id}},
)
trace_id = langfuse_handler.get_trace_id()  # return in API response
```

**Graceful degradation** (FR-025):
```python
def _make_langfuse_handler() -> CallbackHandler | None:
    try:
        return CallbackHandler(...)
    except Exception:
        log.warning("langfuse_unavailable_skipping_trace")
        return None

# Only include callback if handler was created
callbacks = [h for h in [langfuse_handler] if h is not None]
```

---

## Summary of All Decisions

| Area | Decision | Key Implication |
|------|----------|-----------------|
| LangGraph HITL | `AsyncPostgresSaver`, `interrupt()` / `Command(resume=...)` | HITL state stored in existing PG |
| NeMo Guardrails | Per-tenant `LLMRails`, 20s polling hot-reload | `agent/guardrails/{tenant_id}/` dir layout |
| Semantic memory | Mem0 library, per-tenant Qdrant collection | `{tenant_id}_memory` collection naming |
| Batch jobs | rq + Retry + PG source of truth + AOF Redis | `worker/tasks.py` + reconciliation loop |
| LLM gateway | LiteLLM proxy, pinned tag, OTEL Langfuse callback | API key = `LITELLM_MASTER_KEY` in agent |
| Observability | Langfuse v3 → adds ClickHouse + MinIO containers | **compose adds 2 new services** |
