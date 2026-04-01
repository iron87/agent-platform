# Tasks: 2brain AI Agent Platform

**Input**: Design documents from `/specs/001-ai-agent-platform/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize project scaffolding and baseline tooling

- [X] T001 Create Python project metadata and dependency groups in pyproject.toml
- [X] T002 Create developer command targets for bootstrap/test/run in Makefile
- [X] T003 [P] Create base package scaffolding for `agent/`, `api/`, and `worker/` with `__init__.py` files
- [X] T004 [P] Create `.env.example` with documented required environment variables in infra/.env.example
- [X] T005 [P] Create `infra/litellm/config.yaml.template` with aliases `default`, `fast`, `embedding`
- [X] T006 Create single-host compose stack with caddy, postgres, redis, qdrant, litellm, langfuse, clickhouse, minio, agent-api, agent-worker in infra/docker-compose.yml
- [X] T007 Create bootstrap script for secret generation + startup + health wait in infra/bootstrap.sh
- [X] T008 [P] Create Caddy reverse proxy and TLS config in infra/caddy/Caddyfile

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core runtime foundations required by all stories

**⚠️ CRITICAL**: No user story implementation starts before this phase is complete

- [X] T009 Create central settings/config loader with strict env validation in api/config.py
- [X] T010 [P] Create structured logging setup (`structlog` JSON renderer) in api/logging.py
- [X] T011 Create PostgreSQL schema migrations for `tenants`, `agent_definitions`, `jobs`, `approval_requests`, `tenant_policies` in infra/migrations/001_initial_schema.sql
- [X] T012 Create database session and repository primitives in api/db.py
- [X] T013 [P] Create API key auth dependency (`X-API-Key`) with tenant scoping in api/deps.py
- [X] T014 Create shared Pydantic API schemas for run/jobs/approvals/errors in api/models/
- [X] T015 Create base FastAPI app factory with router registration and startup checks in api/main.py
- [X] T016 Create LangGraph shared state and graph registry loader in agent/graphs/state.py and agent/graphs/__init__.py
- [X] T017 [P] Create LiteLLM client wrapper using alias-only model calls in agent/llm.py
- [X] T018 [P] Create Redis session store abstraction with namespaced key patterns in agent/session_store.py
- [X] T019 [P] Create semantic memory abstraction + Mem0/Qdrant implementation in agent/memory.py
- [X] T020 [P] Create per-tenant policy registry and hot-reload loop in agent/policy.py
- [X] T021 Create Langfuse callback wiring with graceful fail-open behavior in agent/observability.py
- [X] T022 Create rq queue factory and enqueue helper with retry/timeouts in worker/queue.py
- [X] T023 Create shared agent service orchestrator for sync/session/async modes in agent/service.py

**Checkpoint**: Foundation complete; user stories are implementable in priority order

---

## Phase 3: User Story 1 - One-Command Platform Bootstrap (Priority: P1) 🎯 MVP

**Goal**: Bring up a fully operational platform from a fresh Docker host using one bootstrap command

**Independent Test**: Run `bash infra/bootstrap.sh` on a fresh host, then call `GET /health` and verify all dependencies report healthy.

### Implementation for User Story 1

- [X] T024 [US1] Implement health dependency probes (postgres/redis/qdrant) in api/routes/health.py
- [X] T025 [US1] Mount unauthenticated `/health` route in api/main.py
- [X] T026 [US1] Add bootstrap idempotency logic (no secret regeneration unless forced) in infra/bootstrap.sh
- [X] T027 [US1] Add startup summary output with generated API key and endpoints in infra/bootstrap.sh
- [X] T028 [US1] Add compose healthchecks and startup ordering for all services in infra/docker-compose.yml
- [X] T029 [US1] Add bootstrap missing-key preflight validation in infra/bootstrap.sh
- [X] T030 [US1] Document bootstrap + health verification flow in specs/001-ai-agent-platform/quickstart.md

**Checkpoint**: Platform can be bootstrapped and verified end-to-end

---

## Phase 4: User Story 2 - Tenant System Invokes an Agent via API (Priority: P2)

**Goal**: Authenticated tenants can synchronously invoke an agent and receive output + trace ID

**Independent Test**: Call authenticated `POST /api/v1/run` with a valid payload and receive `200` with `output` and `trace_id`.

### Implementation for User Story 2

- [X] T031 [P] [US2] Implement sync invocation request/response schemas in api/models/run.py
- [X] T032 [P] [US2] Implement run route handler and error mapping in api/routes/agents.py
- [X] T033 [US2] Implement agent definition lookup + 404 behavior in agent/repositories/agents.py
- [X] T034 [US2] Implement sync execution path + trace propagation in agent/service.py
- [X] T035 [US2] Add route registration for sync invoke endpoint in api/main.py
- [X] T036 [US2] Enforce auth dependency on protected routes in api/routes/agents.py
- [X] T037 [US2] Ensure tenant namespace is attached to execution context in agent/service.py

**Checkpoint**: Synchronous invocation contract works independently

---

## Phase 5: User Story 3 - Conversational Agent Session (Priority: P3)

**Goal**: Session-based invocations preserve and reuse turn history per tenant

**Independent Test**: Send three messages with same `session_id`; third response correctly uses first-turn context.

### Implementation for User Story 3

- [X] T038 [P] [US3] Implement session turn serialization model in agent/models/session.py
- [X] T039 [US3] Implement session history load/append/TTL refresh operations in agent/session_store.py
- [X] T040 [US3] Inject session context into conversational graph execution in agent/graphs/conversational.py
- [X] T041 [US3] Add session-aware mode branching in agent/service.py
- [X] T042 [US3] Add `session_id` validation and tenancy guards in api/models/run.py
- [X] T043 [US3] Add tenant-isolated session key naming enforcement in agent/session_store.py

**Checkpoint**: Stateful conversation works with TTL and tenant isolation

---

## Phase 6: User Story 4 - Tool-Using Agent Multi-Step Task (Priority: P4)

**Goal**: Agent can select and execute tools, then synthesize a final answer with full trace visibility

**Independent Test**: Use deterministic mock tool output; verify response includes tool-derived information and tool span data.

### Implementation for User Story 4

- [X] T044 [P] [US4] Implement web search tool wrapper in agent/tools/web_search.py
- [X] T045 [P] [US4] Implement sandboxed code execution tool wrapper in agent/tools/code_exec.py
- [X] T046 [P] [US4] Implement REST caller tool wrapper with timeout handling in agent/tools/rest_caller.py
- [X] T047 [P] [US4] Implement sandboxed file operations tool wrapper in agent/tools/file_ops.py
- [X] T048 [US4] Implement tool registry + allowlist by agent definition in agent/tools/__init__.py
- [X] T049 [US4] Implement tool-agent graph loop with tool call retries/fail handling in agent/graphs/tool_agent.py
- [X] T050 [US4] Attach tool call spans (args/output/latency/error) to trace callbacks in agent/observability.py

**Checkpoint**: Tool-enabled executions are functional and observable

---

## Phase 7: User Story 5 - Async Batch Processing (Priority: P5)

**Goal**: Tenant can submit long-running jobs and retrieve status/results asynchronously

**Independent Test**: Submit async job, poll until `completed`, retrieve output; restart during `running` and confirm requeue/resume behavior.

### Implementation for User Story 5

- [X] T051 [P] [US5] Implement async submit/status schemas in api/models/jobs.py
- [X] T052 [US5] Implement `POST /jobs` and `GET /jobs/{job_id}` handlers in api/routes/jobs.py
- [X] T053 [US5] Implement job repository CRUD + status transitions in agent/repositories/jobs.py
- [X] T054 [US5] Implement rq task runner entrypoint and callbacks in worker/tasks.py
- [X] T055 [US5] Implement enqueue path from API to rq with retry and timeout policy in worker/queue.py
- [X] T056 [US5] Implement restart reconciliation loop (rq ↔ postgres status sync) in worker/reconcile.py
- [X] T057 [US5] Enforce tenant-scoped job lookup and 404 isolation in api/routes/jobs.py

**Checkpoint**: Async job lifecycle is reliable and tenant-isolated

---

## Phase 8: User Story 6 - Multi-Provider LLM Routing/Fallback (Priority: P6)

**Goal**: Alias-based model routing with automatic provider fallback and trace annotation

**Independent Test**: Force primary alias failure; invocation succeeds via fallback and trace records fallback event.

### Implementation for User Story 6

- [X] T058 [US6] Implement LiteLLM alias/fallback runtime config templating in infra/litellm/config.yaml.template
- [X] T059 [US6] Implement alias validation against `agent_definitions.model_alias` in agent/repositories/agents.py
- [X] T060 [US6] Implement provider fallback warning logging/trace event mapping in agent/llm.py
- [ ] T061 [US6] Add per-alias/per-tenant budget environment wiring in infra/.env.example
- [ ] T062 [US6] Ensure all graph model calls use aliases only (`default`/`fast`/`embedding`) in agent/graphs/conversational.py
- [ ] T063 [US6] Ensure all graph model calls use aliases only (`default`/`fast`/`embedding`) in agent/graphs/tool_agent.py
- [ ] T064 [US6] Ensure all graph model calls use aliases only (`default`/`fast`/`embedding`) in agent/graphs/batch_agent.py

**Checkpoint**: LLM routing is provider-agnostic and resilient

---

## Phase 9: User Story 7 - Trace Review & Replay (Priority: P7)

**Goal**: Every execution is reviewable/replayable by trace ID in observability tooling

**Independent Test**: Execute agent, locate trace by returned `trace_id`, confirm full execution tree and replay linkage.

### Implementation for User Story 7

- [ ] T065 [US7] Add trace metadata propagation (`tenant_id`, `agent_id`, `job_id`) in agent/observability.py
- [ ] T066 [US7] Ensure API responses always include execution `trace_id` in api/models/run.py and api/models/jobs.py
- [ ] T067 [US7] Implement trace-id correlation logging fields in api/logging.py
- [ ] T068 [US7] Implement replay helper endpoint/service integration in api/routes/agents.py and agent/service.py
- [ ] T069 [US7] Add fail-open warning path when Langfuse is unavailable in agent/observability.py

**Checkpoint**: Trace lookup and replay workflow is operational

---

## Phase 10: User Story 8 - Policy Enforcement Before Delivery (Priority: P8)

**Goal**: Per-tenant policies redact/block content and detect injection without restart

**Independent Test**: Configure policy that redacts emails; invoke agent and verify redaction + violation log.

### Implementation for User Story 8

- [ ] T070 [P] [US8] Implement policy models and validation structures in agent/models/policy.py
- [ ] T071 [US8] Implement response redaction and category blocking pipeline in agent/policy.py
- [ ] T072 [US8] Implement injection detection evaluation hook in agent/policy.py
- [ ] T073 [US8] Implement policy application step in service response path in agent/service.py
- [ ] T074 [US8] Implement policy violation structured logging (without raw sensitive values) in agent/policy.py
- [ ] T075 [US8] Implement hot-reload cache refresh and version tracking updates in agent/policy.py
- [ ] T076 [US8] Implement no-policy fast path (zero extra policy calls) in agent/service.py

**Checkpoint**: Policy enforcement is per-tenant, safe, and hot-reloadable

---

## Phase 11: User Story 9 - HITL Approval for High-Risk Tools (Priority: P9)

**Goal**: Approval-gated tool calls pause execution and resume/terminate based on reviewer decision

**Independent Test**: Trigger approval-gated tool, verify `interrupted` state and pending approval; approve and confirm resume; reject and confirm graceful termination.

### Implementation for User Story 9

- [ ] T077 [P] [US9] Implement approval decision/request schemas in api/models/approvals.py
- [ ] T078 [US9] Implement approval repository operations and timeout queries in agent/repositories/approvals.py
- [ ] T079 [US9] Implement LangGraph interrupt/resume integration for gated tools in agent/graphs/tool_agent.py
- [ ] T080 [US9] Implement approval endpoints `GET /approvals/{id}` and `POST /approvals/{id}/decide` in api/routes/approvals.py
- [ ] T081 [US9] Implement approval timeout sweep and default reject handling in worker/approvals_timeout.py
- [ ] T082 [US9] Implement callback/webhook dispatch for approval requests in agent/approvals.py
- [ ] T083 [US9] Record approval lifecycle spans/events in traces in agent/observability.py

**Checkpoint**: HITL safety gate is end-to-end functional

---

## Phase 12: User Story 10 - Tenant CLI Covers the Public API (Priority: P10)

**Goal**: Tenant operators can invoke agents, continue sessions, monitor async jobs, and act on approval requests from a supported CLI instead of hand-writing raw HTTP calls.

**Independent Test**: Configure a CLI profile with `base_url` and `X-API-Key`, then successfully run `2brain run`, `2brain session chat`, `2brain jobs submit|status|wait`, and `2brain approvals get|approve|reject` against the local stack using both human-readable and `--json` output.

### Implementation for User Story 10

- [ ] T084 [P] [US10] Add CLI contract/integration coverage for run, jobs, and approvals flows in tests/cli/test_cli_commands.py
- [ ] T085 [P] [US10] Register the Python `2brain` console entrypoint and root command groups in pyproject.toml, cli/__init__.py, and cli/main.py
- [ ] T086 [P] [US10] Implement profile persistence and `2brain config set` resolution for `--profile`, `--base-url`, and `--api-key` in cli/config.py and cli/commands/config.py
- [ ] T087 [US10] Implement the shared async HTTP API wrapper, auth header injection, and public-contract error mapping in cli/client.py
- [ ] T088 [US10] Implement `2brain run` and `2brain session chat` commands with stable `--json` output in cli/commands/run.py
- [ ] T089 [P] [US10] Implement `2brain jobs submit|status|wait` polling commands in cli/commands/jobs.py
- [ ] T090 [P] [US10] Implement `2brain approvals get|approve|reject` decision commands in cli/commands/approvals.py
- [ ] T091 [P] [US10] Implement Rich/table presenters that preserve the raw API schema for `--json` mode in cli/presenters.py
- [ ] T092 [US10] Create the optional React Ink UI package, API adapter, and interactive screens in packages/tenant-cli-ui/package.json, packages/tenant-cli-ui/src/index.tsx, and packages/tenant-cli-ui/src/screens/
- [ ] T093 [US10] Document CLI installation, profile setup, and end-to-end usage in README.md, specs/001-ai-agent-platform/quickstart.md, and specs/001-ai-agent-platform/contracts/cli-commands.md

**Checkpoint**: Tenants can use the CLI as a first-class consumer of the same authenticated public API contracts.

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: Harden quality, docs, and operational readiness across all stories

- [ ] T094 [P] Add graph unit test coverage for conversational/tool/batch paths in tests/graphs/
- [ ] T095 [P] Add route test coverage for auth/validation/error paths in tests/routes/
- [ ] T096 [P] Add integration scenarios for bootstrap, sync invoke, async job, policy, HITL, and CLI flows in tests/integration/ and tests/cli/
- [ ] T097 Run quickstart scenario validation and update steps for accuracy in specs/001-ai-agent-platform/quickstart.md
- [ ] T098 Validate API contract consistency between implementation and OpenAPI in specs/001-ai-agent-platform/contracts/agent-api.yaml
- [ ] T099 Validate `.env.example` completeness against runtime config loader in infra/.env.example and api/config.py
- [ ] T100 Add final operations runbook notes for restart/upgrade/troubleshooting in docs/operations.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Starts immediately
- **Phase 2 (Foundational)**: Depends on Phase 1; blocks all user stories
- **Phases 3–12 (User Stories)**: Depend on Phase 2 completion; implement in priority order for incremental delivery
- **Phase 13 (Polish)**: Depends on completion of selected user stories

### User Story Dependencies

- **US1 (P1)**: Depends only on foundational setup
- **US2 (P2)**: Depends on US1 operational bootstrap and foundational service scaffolding
- **US3 (P3)**: Depends on US2 invocation path
- **US4 (P4)**: Depends on US2 base invocation and US3 graph/session state primitives
- **US5 (P5)**: Depends on US2 + foundational queue/database layers
- **US6 (P6)**: Depends on US2 + LiteLLM integration from foundational tasks
- **US7 (P7)**: Depends on US2 and observability wiring
- **US8 (P8)**: Depends on US2 and policy subsystem from foundational tasks
- **US9 (P9)**: Depends on US4 tool execution flow + US5 job state management
- **US10 (P10)**: Depends on US2 for sync invocation, US3 for session chat, US5 for async jobs, and US9 for full approval-action coverage

### Within Each User Story

- Data/schema/model tasks before service logic
- Service logic before route wiring
- Route wiring before story-specific integration checks
- Story is complete only when independent test criteria pass

---

## Parallel Opportunities

- **Setup**: T003, T004, T005, T008 can run in parallel after T001
- **Foundational**: T010, T013, T017, T018, T019, T020, T021 can run in parallel once T009/T012 exist
- **US4**: T044–T047 can run in parallel (independent tool modules)
- **US6**: T062–T064 can run in parallel (different graph files)
- **US10**: T084, T085, T086, and T091 can run in parallel; after T087, T089 and T090 can proceed in parallel
- **Polish**: T094–T096 can run in parallel (separate test suites)

### Parallel Example: User Story 4

```bash
Task: "T044 [US4] Implement web search tool wrapper in agent/tools/web_search.py"
Task: "T045 [US4] Implement sandboxed code execution tool wrapper in agent/tools/code_exec.py"
Task: "T046 [US4] Implement REST caller tool wrapper with timeout handling in agent/tools/rest_caller.py"
Task: "T047 [US4] Implement sandboxed file operations tool wrapper in agent/tools/file_ops.py"
```

### Parallel Example: User Story 6

```bash
Task: "T062 [US6] Ensure alias-only calls in agent/graphs/conversational.py"
Task: "T063 [US6] Ensure alias-only calls in agent/graphs/tool_agent.py"
Task: "T064 [US6] Ensure alias-only calls in agent/graphs/batch_agent.py"
```

### Parallel Example: User Story 10

```bash
Task: "T085 [US10] Register the Python `2brain` console entrypoint and root command groups in pyproject.toml, cli/__init__.py, and cli/main.py"
Task: "T086 [US10] Implement profile persistence and `2brain config set` resolution in cli/config.py and cli/commands/config.py"
Task: "T091 [US10] Implement Rich/table presenters that preserve the raw API schema for `--json` mode in cli/presenters.py"
```

---

## Implementation Strategy

### MVP First (US1)

1. Complete Phase 1 + Phase 2
2. Implement Phase 3 (US1) fully
3. Validate independent test for US1 (`bootstrap` + `GET /health`)
4. Demo/deploy as initial operational MVP

### Incremental Delivery

1. Add US2 to enable external invocation contract
2. Add US3 and US4 for core interactive/tool value
3. Add US5 for async production workloads
4. Add US6, US7, US8, and US9 for resilience, observability, compliance, and safety
5. Add US10 to expose the same tenant-facing flows through the CLI and optional Ink UI
6. Execute Phase 13 polish before production handoff

### Suggested MVP Scope

- **Strict MVP**: US1 only (platform bootstraps and is healthy)
- **Practical MVP**: US1 + US2 (bootstrapped platform + callable agent API)
- **CLI delivery slice**: US10 after US2 + US5, with approval subcommands completing once US9 is in place

---

## Format Validation

All tasks in this file follow required checklist format:
- Checkbox prefix: `- [ ]`
- Sequential task IDs: `T001` … `T100`
- `[P]` marker only on parallelizable tasks
- `[US#]` labels only in user story phases
- Every task includes an explicit target file path
