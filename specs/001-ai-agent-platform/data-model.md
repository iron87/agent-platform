# Data Model: 2brain AI Agent Platform

**Phase**: 1 | **Date**: 2026-03-14 | **Plan**: [plan.md](plan.md)

---

## PostgreSQL Entities

### `tenants`

Represents a tenant that has API access to the platform.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, default `gen_random_uuid()` | Tenant identifier (used as namespace prefix everywhere) |
| `name` | `TEXT` | NOT NULL | Human-readable tenant name |
| `api_key_hash` | `TEXT` | NOT NULL, UNIQUE | bcrypt hash of the `X-API-Key` value |
| `approval_endpoint` | `TEXT` | NULLABLE | Webhook URL for HITL approval requests |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |
| `is_active` | `BOOLEAN` | NOT NULL, default `true` | Soft-disable without deletion |

**Relationships**: one-to-many → `jobs`, `approval_requests`

---

### `agent_definitions`

A versioned, stateless definition of an agent. State lives in `sessions` and `jobs`.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK | Agent identifier (used in API paths as `agent_id`) |
| `name` | `TEXT` | NOT NULL, UNIQUE | Slug-style name (e.g., `report-generator`) |
| `model_alias` | `TEXT` | NOT NULL | One of: `default`, `fast`; references LiteLLM alias |
| `prompt_file` | `TEXT` | NOT NULL | Relative path within `agent/prompts/` (e.g., `tool_agent.md`) |
| `graph_type` | `TEXT` | NOT NULL | One of: `conversational`, `tool_agent`, `batch_agent` |
| `tools` | `TEXT[]` | NOT NULL, default `{}` | Tool names this agent may invoke |
| `hitl_tools` | `TEXT[]` | NOT NULL, default `{}` | Subset of `tools` that require human approval |
| `max_execution_seconds` | `INTEGER` | NOT NULL, default `60` | Overrides global `JOB_TIMEOUT_SECONDS` for this agent |
| `semantic_memory_enabled` | `BOOLEAN` | NOT NULL, default `false` | Whether to load/store semantic memory per run |
| `version` | `INTEGER` | NOT NULL, default `1` | Monotonically increasing; bump on any change |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

---

### `jobs`

Authoritative record for every agent invocation (sync and async). rq is the executor; Postgres is the source of truth.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK | Job ID returned to caller |
| `tenant_id` | `UUID` | FK → `tenants.id`, NOT NULL | Tenant scope |
| `agent_id` | `UUID` | FK → `agent_definitions.id`, NOT NULL | |
| `session_id` | `TEXT` | NULLABLE | Non-null for conversational mode |
| `input_payload` | `JSONB` | NOT NULL | Raw input as submitted by caller |
| `status` | `TEXT` | NOT NULL | Enum: `pending`, `running`, `interrupted`, `completed`, `failed` |
| `result` | `JSONB` | NULLABLE | Populated when `status = completed` |
| `error` | `TEXT` | NULLABLE | Populated when `status = failed` |
| `trace_id` | `TEXT` | NULLABLE | Langfuse trace ID, set when trace is created |
| `rq_job_id` | `TEXT` | NULLABLE, UNIQUE | rq job ID for status reconciliation |
| `attempts` | `INTEGER` | NOT NULL, default `0` | Incremented on each rq retry |
| `mode` | `TEXT` | NOT NULL | Enum: `sync`, `async`, `session` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |
| `started_at` | `TIMESTAMPTZ` | NULLABLE | |
| `completed_at` | `TIMESTAMPTZ` | NULLABLE | |

**Indexes**: `(tenant_id, created_at DESC)`, `(rq_job_id)`, `(status)` where `status NOT IN ('completed', 'failed')`

---

### `approval_requests`

An approval gate encountered mid-execution. One per `interrupt()` call.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK | Approval request ID |
| `job_id` | `UUID` | FK → `jobs.id`, NOT NULL | Parent execution |
| `tenant_id` | `UUID` | FK → `tenants.id`, NOT NULL | For auth scoping |
| `tool_name` | `TEXT` | NOT NULL | Tool that triggered the gate |
| `proposed_args` | `JSONB` | NOT NULL | Arguments the agent would pass to the tool |
| `context_summary` | `TEXT` | NULLABLE | Brief context string from graph state |
| `status` | `TEXT` | NOT NULL | Enum: `pending`, `approved`, `rejected`, `timed_out` |
| `timeout_at` | `TIMESTAMPTZ` | NOT NULL | Computed from `HITL_TIMEOUT_SECONDS` at creation |
| `decision_at` | `TIMESTAMPTZ` | NULLABLE | Timestamp of reviewer action |
| `reviewer_id` | `TEXT` | NULLABLE | Opaque reviewer identifier from the decision request |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

**Indexes**: `(job_id)`, `(status, timeout_at)` for timeout sweep

---

### `tenant_policies`

Per-tenant NeMo Guardrails configuration metadata. The actual Colang files live on disk at `agent/guardrails/{tenant_id}/`; this table tracks the active version and reload status.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `tenant_id` | `UUID` | PK, FK → `tenants.id` | One policy record per tenant |
| `version` | `INTEGER` | NOT NULL, default `1` | Incremented on each config update |
| `pii_rules_summary` | `JSONB` | NULLABLE | Human-readable summary of active PII rules (no raw patterns) |
| `blocked_categories` | `TEXT[]` | NOT NULL, default `{}` | Content categories configured as blocked |
| `injection_detection_enabled` | `BOOLEAN` | NOT NULL, default `false` | |
| `colang_hash` | `TEXT` | NULLABLE | SHA-256 of the Colang files for change detection |
| `last_loaded_at` | `TIMESTAMPTZ` | NULLABLE | When the `LLMRails` instance was last rebuilt |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

---

## Redis Keys

### Session (conversational memory)

| Key pattern | Type | TTL | Value |
|-------------|------|-----|-------|
| `{tenant_id}:session:{session_id}:turns` | `LIST` | Sliding `SESSION_TTL_SECONDS` (default 86400 s) | JSON-serialised turn objects |
| `{tenant_id}:session:{session_id}:meta` | `HASH` | Same sliding TTL | `agent_id`, `created_at`, `last_active_at` |

**Turn object shape**:
```json
{"role": "user|assistant", "content": "...", "ts": "2026-03-14T10:00:00Z"}
```

**Access pattern**: `LPUSH` on each new turn; `LRANGE 0 -1` to load history; `EXPIRE` reset on each access (sliding TTL).

### Job queue

| Key | Owner | Description |
|-----|-------|-------------|
| `rq:queue:agent_jobs` | rq | FIFO job queue |
| `rq:job:{rq_job_id}` | rq | rq job metadata |
| `rq:worker:{name}` | rq | Worker heartbeat key (TTL = `WORKER_TTL`) |

---

## Qdrant Collections

| Collection | Naming | Isolation | Managed by |
|------------|--------|-----------|------------|
| `{tenant_id}_memory` | Per tenant | Hard collection boundary | Mem0 library |

**Payload schema** (stored per vector by Mem0):
```json
{
  "id": "<uuid>",
  "text": "Customer prefers weekly reports on Friday.",
  "user_id": "user-123",
  "agent_id": "report-generator",
  "run_id": "<job-id>",
  "created_at": "2026-03-14T10:00:00Z",
  "updated_at": "2026-03-14T10:00:00Z"
}
```

---

## Python Data Models (`agent/` and `api/models/`)

### `MemoryScope` (dataclass — `agent/memory.py`)

```python
@dataclass(frozen=True)
class MemoryScope:
    tenant_id: str
    user_id: str | None = None
    agent_id: str | None = None
    run_id: str | None = None
```

### `MemoryRecord` (dataclass — `agent/memory.py`)

```python
@dataclass(frozen=True)
class MemoryRecord:
    id: str
    text: str
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

### `SemanticMemoryStore` (Protocol — `agent/memory.py`)

```python
class SemanticMemoryStore(Protocol):
    async def upsert_fact(self, *, scope: MemoryScope, text: str,
                          metadata: dict[str, Any] | None = None) -> str: ...
    async def search(self, *, scope: MemoryScope, query: str,
                     limit: int = 5) -> list[MemoryRecord]: ...
    async def delete(self, *, scope: MemoryScope, memory_id: str) -> None: ...
    async def delete_scope(self, *, scope: MemoryScope) -> int: ...
```

### `AgentState` (TypedDict — `agent/graphs/state.py`)

Common state schema shared across all three graph types.

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # Input
    tenant_id: str
    job_id: str
    session_id: str | None
    input: str

    # Conversation
    messages: Annotated[list, add_messages]

    # Tool execution
    pending_tool: str | None
    tool_args: dict[str, Any] | None
    tool_result: str | None

    # Control
    status: str                    # running | interrupted | completed | failed
    approved: bool | None          # set after HITL decision
    error: str | None
```

### API Pydantic models (`api/models/`)

#### `RunRequest` (`api/models/run.py`)

```python
class RunRequest(BaseModel):
    agent_id: UUID
    input: str
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

#### `RunResponse` (`api/models/run.py`)

```python
class RunResponse(BaseModel):
    output: str
    trace_id: str
    job_id: UUID
    session_id: str | None = None
```

#### `JobSubmitRequest` / `JobStatus` (`api/models/jobs.py`)

```python
class JobSubmitRequest(BaseModel):
    agent_id: UUID
    input: str
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class JobStatus(BaseModel):
    job_id: UUID
    status: Literal["pending", "running", "interrupted", "completed", "failed"]
    output: str | None = None
    error: str | None = None
    trace_id: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
```

#### `ApprovalDecision` (`api/models/approvals.py`)

```python
class ApprovalDecision(BaseModel):
    approved: bool
    reason: str | None = None
    reviewer_id: str
```

---

## State Transitions

### Job lifecycle

```
pending ──► running ──► completed
               │
               ├──► interrupted ──► running (on approval)
               │                └──► failed (on rejection / timeout)
               │
               └──► failed
```

### ApprovalRequest lifecycle

```
pending ──► approved ──► (job resumes to running)
        ├──► rejected ──► (job moves to failed / graceful error)
        └──► timed_out ──► (treated as rejected)
```

---

## Validation Rules

| Entity | Field | Rule |
|--------|-------|------|
| `agent_definitions` | `model_alias` | Must be one of the aliases defined in LiteLLM config |
| `agent_definitions` | `hitl_tools` | Must be a subset of `tools` |
| `agent_definitions` | `graph_type` | Must be `conversational`, `tool_agent`, or `batch_agent` |
| `jobs` | `status` | Transitions only forward (no `completed → running`); enforced by application layer |
| `jobs` | `session_id` | Required when `mode = session`; must be null when `mode = async` |
| `approval_requests` | `status` | Only `pending` requests can be approved/rejected/timed out |
| `RunRequest` | `input` | Max 32 768 tokens (enforced before graph execution) |
| `ApprovalDecision` | `reviewer_id` | Must be non-empty string |

---

## CLI-Local Entities

The CLI does **not** introduce new server-side persistence tables. It adds a small local configuration model and an in-memory interaction state for terminal workflows.

### `CLIProfile` (local config file)

| Field | Type | Required | Description |
|------|------|----------|-------------|
| `name` | `str` | yes | Human-friendly profile alias such as `local-dev` or `acme-prod` |
| `base_url` | `AnyHttpUrl` | yes | Base URL for the 2brain API |
| `api_key` | `SecretStr` | yes | Tenant-scoped API key sent via `X-API-Key` |
| `default_agent_id` | `UUID \| None` | no | Optional default agent for run/session commands |
| `output_mode` | `Literal["table", "json"]` | yes | Default rendering mode |
| `poll_interval_seconds` | `int` | yes | Default polling cadence for jobs and approvals |
| `interactive_ui` | `bool` | yes | Whether to prefer Ink mode when a TTY is available |

### `CLIInvocationState` (interactive session only)

| Field | Type | Description |
|------|------|-------------|
| `active_screen` | `Literal["home", "chat", "jobs", "approvals"]` | Current Ink view |
| `session_id` | `str \| None` | Current conversation namespace |
| `job_id` | `UUID \| None` | Currently selected async job |
| `pending_approval_id` | `UUID \| None` | Currently selected approval request |
| `last_trace_id` | `str \| None` | Latest trace surfaced to the operator |
| `last_error` | `str \| None` | Last API or validation error shown in the UI |

### CLI request wrappers

The Ink CLI (including its non-interactive `--json` mode) will serialize the **same payload shapes** already defined for `RunRequest`, `JobSubmitRequest`, `JobStatus`, and `ApprovalDecision`. No CLI-only server contract is introduced.
