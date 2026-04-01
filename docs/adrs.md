# 2brain ADRs (Reconstructed)

These ADRs reconstruct the main implementation decisions currently visible in the codebase, specs, migrations, and runtime behavior.
They are written after the fact to capture why the platform looks the way it does today.

---

## ADR-001 — Use a self-hosted single-host Docker Compose stack

- **Status**: Accepted
- **Context**: The platform must be easy to bootstrap on a fresh machine, stay cloud-agnostic, and run locally for development and demos.
- **Decision**: Keep the operational topology in `infra/docker-compose.yml` and `infra/docker-compose.light.yml`, with `bootstrap.sh` / `bootstrap-light.sh` generating secrets, normalizing `.env`, and waiting for health checks.
- **Consequences**: Operations stay simple and repeatable; horizontal scaling is deferred beyond v1.

## ADR-002 — Use `tenant` as the isolation boundary

- **Status**: Accepted
- **Context**: The earlier `client` term was too agency-specific and did not fit internal-team or broader B2B usage well.
- **Decision**: Standardize on `tenants`, `tenant_id`, and `tenant_policies`, with auth and runtime scoping centered on the tenant entity.
- **Consequences**: The platform is more generic and reusable; an idempotent migration (`infra/migrations/002_tenants_rename.sql`) is required for existing environments.

## ADR-003 — Keep FastAPI routes thin and centralize orchestration in `AgentService`

- **Status**: Accepted
- **Context**: Sync, session, and async execution should behave consistently without duplicating logic across HTTP endpoints.
- **Decision**: `api/routes/*.py` handle HTTP concerns only; `agent/service.py` loads agent definitions, prepares execution state, chooses graphs, and coordinates downstream services.
- **Consequences**: Cleaner separation of concerns and easier testing; the service layer becomes the primary orchestration point.

## ADR-004 — Implement agents as separate LangGraph workflows

- **Status**: Accepted
- **Context**: Conversational runs, tool-using runs, and batch/async runs have different execution shapes and state requirements.
- **Decision**: Register distinct graph builders in `agent/graphs/__init__.py` and select them via `agent_definitions.graph_type`.
- **Consequences**: Each workflow remains easier to reason about and extend; future HITL/resume behavior has a natural home.

## ADR-005 — Route all LLM calls through LiteLLM aliases only

- **Status**: Accepted
- **Context**: The runtime should avoid provider-specific coupling and support fallback/reconfiguration without changing agent code.
- **Decision**: Restrict the runtime to the aliases `default`, `fast`, and `embedding`; render the LiteLLM config from `.env` at container start; use `default -> fast` fallback by configuration.
- **Consequences**: Provider switching stays configuration-only; invalid `model_alias` values are rejected early.

## ADR-006 — Use Redis and RQ for runtime state and async execution, with PostgreSQL as the durable source of truth

- **Status**: Accepted
- **Context**: The platform needs simple async job processing and session persistence on a single host without adding heavier workflow infrastructure.
- **Decision**: Store session turns in Redis, enqueue jobs through RQ, and persist job lifecycle/state in PostgreSQL.
- **Consequences**: The runtime is operationally lightweight; reconciliation logic is needed to keep Redis/RQ and PostgreSQL aligned.

## ADR-007 — Namespace semantic memory per tenant in Qdrant / Mem0

- **Status**: Accepted
- **Context**: Semantic memory must not leak across tenants, and destructive operations must stay scoped safely.
- **Decision**: Use per-tenant namespaces/collection names such as `{tenant_id}_memory` through `agent/memory.py`.
- **Consequences**: Isolation is stronger; operational management of collections becomes slightly more explicit.

## ADR-008 — Keep policy enforcement and observability fail-open

- **Status**: Accepted
- **Context**: Guardrails or tracing outages should not block the primary execution path for tenants.
- **Decision**: `agent/policy.py` and `agent/observability.py` log warnings and continue when guardrails or Langfuse are unavailable.
- **Consequences**: Runtime availability is prioritized; some policy/tracing fidelity may be lost during outages.

## ADR-009 — Expose tools through explicit per-agent allowlists

- **Status**: Accepted
- **Context**: Tool usage needs safety boundaries and a clear contract per agent definition.
- **Decision**: `agent_definitions.tools` and `hitl_tools` determine which runtime tools are available, and the tool graph enforces those allowlists.
- **Consequences**: Capabilities stay predictable and auditable; tool access requires intentional configuration.

## ADR-010 — Prefer idempotent upgrades and local reruns

- **Status**: Accepted
- **Context**: The repo is frequently re-bootstrapped during development and refactoring, so rerunning setup must be safe.
- **Decision**: Make bootstrap scripts idempotent, preserve existing secrets by default, and write migrations so they can be applied repeatedly without harm.
- **Consequences**: Local/dev workflows are safer and more repeatable; bootstrap and migration scripts carry a bit more logic.

## ADR-011 — Build the tenant CLI with React Ink while keeping it on the public API

- **Status**: Accepted (planned / partially documented)
- **Context**: The CLI should provide a richer terminal UX and the product direction is to avoid a separate Python CLI surface.
- **Decision**: The planned `2brain` CLI is Ink/TypeScript-based, but it still calls the same `/run`, `/jobs`, and approval endpoints used by HTTP integrators.
- **Consequences**: The operator UX is richer, and the public API remains the single integration contract; the repo now carries a Node/TypeScript CLI package in addition to the Python backend.
