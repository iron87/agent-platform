# Feature Specification: 2brain AI Agent Platform

**Feature Branch**: `001-ai-agent-platform`
**Created**: 2026-03-13
**Status**: Draft
**Input**: User description: "A self-hosted platform for an AI engineering agency to design, deploy, and operate AI agents for tenants."

## Clarifications

### Session 2026-04-01

- Q: What API surface should the CLI cover? → A: The CLI must cover all tenant-facing API flows: synchronous invocation, asynchronous job submission and status polling, session-based conversations, and approval actions. Purely operational/admin endpoints remain outside the initial CLI scope.
- Q: What implementation stack should the CLI use? → A: The CLI should be implemented primarily with **React Ink / TypeScript**, not as a Python CLI. It must still support `--json` output for scripting and automation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One-Command Platform Bootstrap (Priority: P1)

An agency engineer with a fresh Linux host that has Docker installed runs a
single bootstrap script. Within minutes the platform is fully operational: all
services are running, all databases are initialised, and all internally-used
secrets have been generated automatically. The only inputs the engineer provided
were the externally-sourced API keys (LLM provider keys). After bootstrap the
engineer can point a REST client at the platform and invoke an agent immediately.

**Why this priority**: Without a working platform there is nothing else to test
or deliver. This story is the foundation every other story depends on. It also
directly validates the cloud-agnostic, single-command operational requirement.

**Independent Test**: Run the bootstrap script on a fresh Docker host with only
LLM provider keys set, wait for completion, then call `GET /health` and receive
200 with all dependencies reported healthy.

**Acceptance Scenarios**:

1. **Given** a fresh Linux host with Docker installed and no prior configuration, **When** the engineer runs `./bootstrap.sh` and provides LLM provider API keys when prompted, **Then** all platform services start successfully, health endpoints return 200, and the bootstrap script prints an access summary with the generated API key.
2. **Given** the platform is running, **When** the engineer calls `GET /health`, **Then** the response includes the status of every critical dependency and returns 200 only if all are reachable, or 503 if any is unreachable with the failing dependency identified.
3. **Given** the bootstrap is run a second time on a host where the platform is already running, **When** the script completes, **Then** no data is lost and no secrets are regenerated unless explicitly requested.
4. **Given** a required externally-sourced API key is not provided, **When** bootstrap is attempted, **Then** the script exits with a clear error identifying which keys are missing before any service starts.

---

### User Story 2 - Client System Invokes an Agent via API (Priority: P2)

A tenant system (a backend service or integration layer built by a tenant)
sends a request to the platform's external API to invoke an agent. The platform
authenticates the request, executes the agent, and returns the result along with
a trace identifier the caller can use to reference the execution. The caller
never needs to know which LLM provider was used or how the agent was
implemented.

**Why this priority**: This is the primary integration contract. Every other
capability is only useful if tenant systems can reliably invoke agents. This
story defines the external boundary of the platform.

**Independent Test**: Send an authenticated `POST /agents/{agent_id}/invoke`
request with a valid payload and receive a structured response with a result and
`trace_id` — verifiable without any memory, policy, or HITL features enabled.

**Acceptance Scenarios**:

1. **Given** a valid `X-API-Key` header and well-formed request body, **When** the caller calls `POST /agents/{agent_id}/invoke`, **Then** the platform returns a structured response containing the agent's output and a `trace_id` within an acceptable time bound.
2. **Given** an `X-API-Key` header that is absent or invalid, **When** the caller calls any protected endpoint, **Then** the platform returns 401 with no execution occurring.
3. **Given** a request with a malformed body (missing required fields), **When** the caller calls the invocation endpoint, **Then** the platform returns 422 with a structured description of every validation error.
4. **Given** an `agent_id` that does not exist, **When** the caller invokes it, **Then** the platform returns 404 with a human-readable error message.
5. **Given** a tenant belongs to tenant A, **When** the invocation completes, **Then** the stored execution data (memory, trace, job records) is accessible only under tenant A's namespace and is not visible to tenant B's API calls.

---

### User Story 3 - Conversational Agent Session (Priority: P3)

A tenant system starts a conversation with an agent by providing a session
identifier. On each subsequent turn the agent receives the accumulated
conversation history from that session, allowing it to respond coherently to
context established in earlier turns. The session persists until explicitly
cleared or it expires.

**Why this priority**: Stateful back-and-forth interaction is the most common
usage pattern for AI agents deployed in tenant products. Without it most
real-world use cases cannot be served.

**Independent Test**: Send three sequential messages in the same session where
the third message references information from the first, and verify the agent
responds correctly to the reference — fully testable without semantic memory,
policy, or HITL.

**Acceptance Scenarios**:

1. **Given** a new session ID, **When** the caller sends the first message, **Then** the agent responds and the turn is recorded in the session's conversational memory.
2. **Given** a session with prior turns already recorded, **When** the caller sends a follow-up message, **Then** the agent receives the prior turns as context and can respond with awareness of what was said earlier.
3. **Given** a session that has not been used for longer than the configured session TTL, **When** a new message arrives in that session, **Then** the session is treated as new (no stale context is injected). The TTL must be configurable per tenant.
4. **Given** two tenants (tenant A and tenant B) that happen to use the same session identifier string, **When** each sends a message, **Then** each agent receives only the history from its own tenant's session — cross-tenant history leakage is impossible.

---

### User Story 4 - Tool-Using Agent Completes a Multi-Step Task (Priority: P4)

An agency engineer configures an agent with a set of tools (web search, code
execution, REST API caller, file reader/writer). A tenant system sends a task
description. The agent autonomously decides which tools to invoke, in what
order, and with what inputs, then synthesises the tool outputs into a final
answer. The caller receives the answer and a full trace of every tool call made.

**Why this priority**: Tool-using agents are the primary mechanism for extending
agent capability beyond pure language generation. They enable the high-value,
automation-heavy use cases the agency is built to deliver.

**Independent Test**: Configure an agent with a mock web-search tool that
returns deterministic results. Send a task that requires the search tool. Verify
the response incorporates the mock search result and the trace records the tool
call — testable entirely offline without real external APIs.

**Acceptance Scenarios**:

1. **Given** an agent configured with one or more tools, **When** the task requires information only available via a tool, **Then** the agent invokes the appropriate tool, incorporates its output, and returns a synthesised answer.
2. **Given** a tool call that fails (timeout, error response), **When** the agent receives the failure, **Then** the agent handles it gracefully (retry, fallback, or clear error to caller) rather than crashing.
3. **Given** a tool that is sandboxed (code execution, filesystem writes), **When** the agent invokes it, **Then** execution is isolated so that a misbehaving tool cannot affect the host environment or other agents.
4. **Given** a tool invocation is completed, **When** the trace is later queried, **Then** the trace contains the tool name, input arguments, output, and latency for every tool call made in that execution.

---

### User Story 5 - Batch Job Submitted and Processed Asynchronously (Priority: P5)

A tenant system submits a long-running job (e.g., analyse a large document,
generate a weekly report) and immediately receives a job ID. The caller
periodically polls for status or receives a webhook notification when the job
completes. The job is processed in the background and the result is retrievable
via the job ID. If the platform restarts while a job is running, the job resumes
or is re-queued cleanly.

**Why this priority**: Many high-value automation tasks run too long for a
synchronous HTTP call. Async batch processing is required for the agency to
serve pipeline-oriented tenant use cases.

**Independent Test**: Submit a job, receive a job ID, poll status until
`completed`, retrieve result — all verifiable without conversational memory or
policy features, using an agent that performs minimal work.

**Acceptance Scenarios**:

1. **Given** a valid job submission request, **When** the caller calls the async invocation endpoint, **Then** the platform returns immediately with a `job_id` and a status of `pending` or `queued`.
2. **Given** a submitted job, **When** the caller polls `GET /jobs/{job_id}`, **Then** the response reflects the current status (`pending`, `running`, `completed`, `failed`) and, when completed, includes the result.
3. **Given** a job in progress and the platform restarts, **When** the platform comes back online, **Then** the job is either resumed or re-queued without manual intervention, with no data loss.
4. **Given** two tenants submit jobs concurrently, **When** both jobs are processing, **Then** a runaway or resource-intensive job from tenant A does not prevent tenant B's jobs from making progress.
5. **Given** a completed job result, **When** a tenant from a different tenant attempts to retrieve it using the job ID, **Then** the platform returns 404 — result access is isolated by tenant.

---

### User Story 6 - Multi-Provider LLM Routing and Fallback (Priority: P6)

An agency engineer configures which LLM provider and model backs each logical
model alias (`default`, `fast`, `embedding`). If the primary provider for an
alias is temporarily unavailable, the platform automatically retries with a
configured fallback provider. Agent code never changes when the underlying
provider changes — only the routing configuration is updated.

**Why this priority**: Provider lock-in is an existential risk for an agency.
The ability to switch or fall back between providers without code changes enables
cost optimisation, resilience, and support for on-premise models.

**Independent Test**: Configure `default` to a primary provider and a fallback
provider. Simulate a primary provider failure. Invoke an agent using the
`default` alias. Verify the response was produced and the trace records that the
fallback provider was used.

**Acceptance Scenarios**:

1. **Given** a model alias is configured with a primary provider and the provider is available, **When** an agent invokes the alias, **Then** the request is routed to the primary provider.
2. **Given** the primary provider for an alias returns an error or timeout, **When** the platform retries, **Then** the request is automatically routed to the configured fallback provider and a warning is recorded in the trace.
3. **Given** no fallback is configured and the primary provider is unavailable, **When** an agent invokes the alias, **Then** the platform returns a clear error to the caller indicating the LLM provider is unavailable.
4. **Given** an engineer updates the provider mapping for an alias in configuration, **When** the routing service is restarted, **Then** subsequent agent invocations use the new provider without any agent code change.

---

### User Story 7 - Trace Review and Replay (Priority: P7)

An agency engineer notices a tenant report that an agent returned an unexpected
response. The engineer opens the observability UI, finds the trace by `trace_id`
or by filtering on time range and agent ID, and sees the full execution tree:
the input, every LLM call with its prompt and response, every tool invocation
with its arguments and output, the final response, and the latency of each step.
The engineer can replay the trace input to reproduce the issue.

**Why this priority**: Without this capability engineers cannot diagnose failures
in production, making the platform operationally blind. Observability is a core
reliability requirement, not a nice-to-have.

**Independent Test**: Execute an agent. Open the observability UI, find the
generated trace, and verify it contains the input, at least one LLM call record,
and the output — verifiable immediately after a single agent execution.

**Acceptance Scenarios**:

1. **Given** an agent execution completes (success or failure), **When** the engineer searches for its `trace_id` in the observability UI, **Then** the full execution tree is displayed including input, LLM calls, tool calls, output, per-step latency, and any errors.
2. **Given** a trace from a failed execution, **When** the engineer selects replay, **Then** the same input is re-submitted to the agent and a new trace is generated linked to the original.
3. **Given** the trace contains an LLM call, **When** the engineer inspects it, **Then** the exact prompt sent to the model and the raw model response are both visible.
4. **Given** a trace ID is included in a tenant-facing API response, **When** the caller shares that ID with the agency, **Then** the engineer can look it up directly in the UI.

---

### User Story 8 - Policy Check Before Response Delivery (Priority: P8)

An agency engineer configures a policy for a specific tenant that defines: which
PII patterns to detect and redact (e.g., email addresses, phone numbers), which
content categories to block, and whether to scan for prompt injection attempts.
Every agent response produced for that tenant is automatically evaluated against
the policy before being returned to the caller. Policy violations are logged. The
policy can be updated without redeploying the platform.

**Why this priority**: Agency tenants in regulated industries require data
protection guarantees. Policy enforcement is a compliance and trust requirement
for the agency to operate in those verticals.

**Independent Test**: Configure a policy that redacts email addresses. Invoke an
agent with an input designed to produce an email address in the response. Verify
the returned response has the email address redacted and the violation is logged
— testable without HITL or batch features.

**Acceptance Scenarios**:

1. **Given** a tenant policy with PII redaction rules, **When** the agent response contains a value matching a redaction rule, **Then** the value is replaced with a redaction marker before the response reaches the caller and the raw value is not logged.
2. **Given** a tenant policy with a blocked content category, **When** the agent response falls into that category, **Then** the response is suppressed, the caller receives an error indicating policy violation, and the violation is recorded.
3. **Given** the agent input contains a suspected prompt injection attempt, **When** the policy layer detects it, **Then** the execution is flagged in the trace and optionally blocked depending on the tenant's policy configuration.
4. **Given** an engineer updates a tenant's policy configuration, **When** the change takes effect without platform restart, **Then** subsequent invocations for that tenant use the updated rules immediately.
5. **Given** a tenant that has no policy configured, **When** an agent is invoked for that tenant, **Then** responses pass through unmodified with no degradation in performance.

---

### User Story 9 - Human Approval for High-Risk Tool Calls (Priority: P9)

An agency engineer marks certain tool calls (e.g., "send email", "write to
external system", "initiate payment") as requiring human approval. When an agent
reaches one of those tool calls during execution, it pauses and routes an
approval request to a configured endpoint or the platform's internal approval
UI. A human reviewer sees the pending action, including the full context, and
either approves or rejects it. If approved the agent continues; if rejected the
agent receives the rejection and can handle it gracefully.

**Why this priority**: Irreversible or high-risk tool calls without human
oversight are a liability risk for the agency and its tenants. This capability
is a safety gate for production deployments.

**Independent Test**: Configure a tool as requiring approval. Invoke an agent
that triggers that tool. Verify the execution pauses with a `pending_approval`
status. Submit an approval decision. Verify the agent resumes (or terminates
gracefully on rejection) and the trace reflects the approval event.

**Acceptance Scenarios**:

1. **Given** a tool is configured as requiring approval, **When** the agent decides to invoke that tool, **Then** execution pauses, the job status transitions to `pending_approval`, and an approval request is sent to the configured endpoint with full context (agent ID, tool name, proposed arguments, session summary).
2. **Given** a pending approval request, **When** a reviewer submits an approval, **Then** the agent resumes execution from the paused point and proceeds with the tool call.
3. **Given** a pending approval request, **When** a reviewer rejects it, **Then** the agent receives the rejection, handles it according to its design (e.g., informs the user that the action was declined), and the trace records the rejection event.
4. **Given** no reviewer acts on a pending approval within the configured timeout window, **When** the timeout expires, **Then** the approval is treated as rejected, the agent is notified, and the caller is informed.
5. **Given** an agent that requires no approval-gated tools, **When** it executes, **Then** there is no performance or latency overhead from the approval mechanism.

---

### Edge Cases

- What happens when an LLM provider rate-limits the platform mid-execution?
- How does the system handle an agent that enters an infinite tool-calling loop?
- What happens if the job queue is full when a batch job is submitted?
- How does the platform behave if the observability service is unavailable — does it degrade gracefully or block agent execution?
- What happens when a policy configuration file is malformed on startup?
- How does the system handle a human-approval timeout when the agent has already modified external state before being paused?
- What occurs when two concurrent requests use the same session ID for a conversational agent?

## Requirements *(mandatory)*

### Functional Requirements

**Agent Execution**

- **FR-001**: The platform MUST support three invocation modes: synchronous (caller waits for result), session-based (stateful turns within a named session), and asynchronous (caller receives a job ID and polls for completion).
- **FR-002**: All three invocation modes MUST use the same underlying agent execution model. The mode is determined by the API endpoint called, not by the agent definition.
- **FR-003**: The platform MUST expose a `POST /agents/{agent_id}/invoke` endpoint for synchronous invocation and `POST /agents/{agent_id}/invoke-async` for asynchronous invocation.
- **FR-004**: Synchronous invocations MUST return the agent result and a `trace_id` in a single response.
- **FR-005**: Asynchronous jobs MUST be retrievable via `GET /jobs/{job_id}` with a status field reflecting `pending`, `running`, `completed`, or `failed`.
- **FR-006**: An in-progress async job MUST survive a platform restart: it MUST be re-queued or resumed without manual intervention.
- **FR-007**: The platform MUST enforce a configurable maximum execution time per agent invocation. Executions exceeding the limit MUST be terminated and the caller notified.
- **FR-008**: All agent invocations MUST produce a trace. An invocation MUST NOT complete without a trace record being created.

**Platform Bootstrap and Operations**

- **FR-009**: The platform MUST be fully operational after running a single bootstrap script on a fresh Linux host with Docker installed, with no manual steps required after script completion.
- **FR-010**: The bootstrap script MUST generate all internally-used secrets automatically. Only externally-sourced API keys (LLM provider keys) require manual input.
- **FR-011**: The platform MUST be upgradeable by changing a container image tag and issuing a rolling restart command. Minor version upgrades MUST NOT require manual data migration steps.
- **FR-012**: The platform MUST run identically in development and production environments. The only permitted per-environment differences are: domain name, whether the reverse proxy TLS termination is active, and log verbosity.
- **FR-013**: Every required environment variable MUST be documented and present in `.env.example` with a safe default value and an explanatory comment.

**LLM Access**

- **FR-014**: All agent LLM calls MUST be routed through a centralised LLM proxy. Agents MUST specify model aliases (e.g., `default`, `fast`, `embedding`), never provider-specific model strings.
- **FR-015**: The LLM proxy MUST support configuring fallback providers per alias. If the primary provider fails, the proxy MUST automatically retry with the fallback and record the event.
- **FR-016**: The LLM proxy MUST enforce configurable per-tenant and per-model spending limits. Requests that would exceed the limit MUST be rejected with a clear error.
- **FR-017**: The platform MUST support at minimum: Anthropic, OpenAI, and locally-hosted model endpoints. Adding a new provider MUST require only a configuration change, not a code change.

**Memory**

- **FR-018**: The platform MUST maintain conversational memory per session per tenant. Each turn in a session MUST be stored and supplied as context on subsequent turns.
- **FR-019**: Sessions MUST expire after a configurable idle TTL. Expired session memory MUST be treated as cleared on the next invocation.
- **FR-020**: The platform MUST support semantic memory: an agent MUST be able to store a fact as an embedding and later retrieve the most semantically relevant stored facts given a query.
- **FR-021**: Semantic memory MUST persist indefinitely across sessions until explicitly deleted. It MUST be isolated per tenant.

**Observability**

- **FR-022**: Every agent execution MUST produce a structured trace stored in the observability service. The trace MUST capture: input, every LLM call (prompt, response, model alias used, latency), every tool call (name, arguments, output, latency), final output, total latency, and any errors.
- **FR-023**: Traces MUST be searchable and reviewable in the observability UI without access to raw logs or infrastructure.
- **FR-024**: Each trace MUST have a unique `trace_id` that is returned in the API response and can be used to retrieve the full trace directly.
- **FR-025**: The observability service being unavailable MUST NOT block agent execution. The platform MUST degrade gracefully, recording a warning that the trace could not be stored.

**Policy Enforcement**

- **FR-026**: The platform MUST apply a configurable policy check to every agent response before returning it to the caller.
- **FR-027**: Policy MUST support: PII pattern detection and redaction, content category blocking, and prompt injection detection.
- **FR-028**: Policy rules MUST be configurable per tenant without redeploying the platform. Configuration changes MUST take effect without a full restart.
- **FR-029**: All policy violations MUST be logged with the trace ID, tenant ID, violation type, and (for redaction) a description of what was detected — but NOT the raw sensitive value.
- **FR-030**: Clients with no configured policy MUST experience no performance overhead from the policy layer.

**Tenant Isolation**

- **FR-031**: All tenant data (session memory, semantic memory, job queues, traces) MUST be stored under a namespace keyed by `tenant_id`. Cross-namespace access MUST be impossible by design.
- **FR-032**: A misbehaving or resource-intensive agent execution for one tenant MUST NOT prevent other tenants' agents from running.
- **FR-033**: API keys MUST be scoped to a single tenant. A valid API key for tenant A MUST NOT grant access to tenant B's resources.

**Human-in-the-Loop**

- **FR-034**: Any tool call MAY be designated as requiring human approval in the platform's tool configuration. This designation applies platform-wide for that tool.
- **FR-035**: When an agent reaches an approval-gated tool call, execution MUST pause. The job status changes to `pending_approval` and an approval request is sent to the tenant's configured approval endpoint.
- **FR-036**: The approval request MUST include: agent ID, tool name, proposed arguments, session context summary, and the job ID.
- **FR-037**: The platform MUST expose endpoints for a reviewer to submit an approval or rejection decision for a pending approval request.
- **FR-038**: Approvals MUST have a configurable timeout. On timeout, the decision MUST default to rejected and the agent MUST be notified.
- **FR-039**: The full approval lifecycle (pause, request sent, decision received, agent resumed or terminated) MUST be recorded in the execution trace.

**Security**

- **FR-040**: Every endpoint except `GET /health` MUST require authentication via `X-API-Key` header. Unauthenticated requests MUST return 401.
- **FR-041**: API keys and all secrets MUST be sourced exclusively from environment variables. They MUST NOT appear in source code, logs, or trace data.
- **FR-042**: Tools that execute code or write to the filesystem MUST run in an isolated sandbox. Sandbox failures MUST be reported as tool errors, not platform crashes.

**CLI Access**

- **FR-043**: The platform MUST provide a CLI interface that exposes all tenant-facing API operations, including synchronous invocation, session-based conversations, asynchronous job submission/status retrieval, and approval actions.
- **FR-044**: The CLI MUST call the same external API contracts used by HTTP integrators rather than bypassing authentication, policy checks, or tenant-isolation controls.

### Key Entities

- **Agent**: A named, versioned definition specifying: which model alias it uses, which tools it can invoke, which system prompt it loads, its memory configuration, and its approval-gated tools. An agent definition is stateless; state lives in sessions and jobs.
- **Session**: A named conversation context scoped to an agent and a tenant. Contains: session ID, tenant ID, agent ID, ordered list of turns (each turn has role, content, timestamp), TTL, and last-active timestamp.
- **Job**: An asynchronous execution record. Contains: job ID, tenant ID, agent ID, input payload, status, created-at, started-at, completed-at, result (when complete), error (when failed), and trace ID.
- **Trace**: An immutable record of one complete agent execution. Contains: trace ID, agent ID, tenant ID, total latency, input, output, and an ordered list of spans — each span records the operation type, inputs, outputs, latency, and any error.
- **ApprovalRequest**: A paused execution awaiting human decision. Contains: request ID, job ID, tool name, proposed arguments, context summary, status (`pending`, `approved`, `rejected`, `timed_out`), decision timestamp, and reviewer identifier.
- **TenantPolicy**: Per-tenant policy configuration. Contains: tenant ID, list of PII detection rules (pattern and redaction marker), list of blocked content categories, prompt injection detection flag, and policy version.
- **ModelAlias**: Mapping of a logical alias name to: primary provider and model, optional fallback provider and model, and optional per-alias spend limit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new platform instance is fully operational — all health checks passing, an agent invocable — within 10 minutes of running the bootstrap script on a fresh host with Docker installed.
- **SC-002**: Any synchronous agent invocation (not blocked on human approval) returns a response within 30 seconds for 95% of requests under normal load.
- **SC-003**: A batch job that survives a platform restart is automatically re-queued and begins processing within 60 seconds of the platform coming back online, with no manual intervention.
- **SC-004**: An engineer can locate a specific trace by ID in the observability UI and view the complete execution tree within 10 seconds of entering the trace ID.
- **SC-005**: A policy configuration change for a tenant takes effect for all subsequent invocations within 30 seconds of being applied, without a platform restart.
- **SC-006**: 100% of agent executions that complete (success or failure) have a retrievable trace. Zero executions may complete without a trace record.
- **SC-007**: A runaway job from one tenant does not prevent agents from other tenants completing their executions within their normal time bounds.
- **SC-008**: All internally-used secrets are generated with cryptographic randomness by the bootstrap script. No default or predictable secret values exist after bootstrap.
- **SC-009**: Engineers unfamiliar with the platform internals can identify all required configuration values by reading `.env.example` alone.
- **SC-010**: Swapping the LLM provider behind a model alias requires only a configuration change (no code change, no rebuild), taking effect on the next routing service restart.

### Assumptions

- The platform is deployed on a single host. Horizontal scaling across multiple hosts is out of scope.
- Streaming (token-by-token) responses are not required in this version.
- There is no end-user-facing frontend. All interaction is API-to-API.
- Fine-tuning and model training are out of scope. Only inference is in scope.
- The host running Docker has outbound internet access for pulling images and reaching cloud LLM APIs. Air-gapped deployment is a future concern.
- Per-tenant spend limits are tracked at the LLM proxy level, not enforced at a billing or payment system level.
- The approval UI referenced in the HITL user story is the observability platform's built-in interface; no separate bespoke approval UI is built as part of this feature.
- Engineers access the observability UI using credentials managed by that tool's own authentication, independent of the `X-API-Key` scheme.
