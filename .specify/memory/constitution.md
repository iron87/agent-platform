<!--
SYNC IMPACT REPORT
==================
Version change  : (none) → 1.0.0  (initial ratification)
Modified        : n/a — first creation
Added sections  :
  - I.   Architecture
  - II.  Code Quality
  - III. Testing Standards
  - IV.  Observability Standards
  - V.   Security
  - VI.  LLM Interaction
  - VII. Extensibility
  - Governance
Removed sections: n/a
Templates reviewed:
  ✅  .specify/templates/plan-template.md
        Constitution Check gate references are dynamic ("[Gates determined
        based on constitution file]"): no changes needed.
  ✅  .specify/templates/spec-template.md
        No hardcoded principle names; template is constitution-agnostic.
  ✅  .specify/templates/tasks-template.md
        Task phases reference observability/testing patterns consistent with
        principles III and IV. No structural changes required.
  ✅  .specify/templates/constitution-template.md
        Source template only; not modified.
Follow-up TODOs:
  - TODO(RATIFICATION_DATE): If the true governance ratification date differs
    from 2026-03-13, update the Version line accordingly.
  - TODO(GOVERNANCE_APPROVAL): Define who has authority to ratify amendments
    (team lead, RFC process, etc.) once the team governance process is agreed.
-->

# 2brain Platform Constitution

## I. Architecture

**Cloud Agnostic First**
No managed cloud service may be a hard dependency. Every component MUST run in
a Docker container on any Linux host. Cloud-specific services (S3, RDS, GCS,
etc.) are permitted only as optional overrides configured exclusively via
environment variables. The platform MUST be fully operational without any cloud
account.

**Single Compose File as Source of Truth**
The entire platform MUST be startable with a single `docker compose up` command.
No multi-step manual procedures are acceptable after the bootstrap sequence.
`docker-compose.yml` (or `compose.yml`) is the authoritative runtime definition.

**Explicit over Implicit**
All configuration is via environment variables documented exhaustively in
`.env.example`. No hidden defaults that differ between environments are
permitted. Every variable that changes behaviour between local and production
MUST appear in `.env.example` with a safe default and an explanatory comment.

**One Service, One Responsibility**
Each container does exactly one thing. Bundling multiple concerns (e.g., worker
+ API in one container) is prohibited. Service boundaries are enforced at the
container level, not only at the code level.

## II. Code Quality

**Python 3.12+**
All Python code MUST target Python 3.12 or newer. Modern type syntax is
mandatory: use `X | Y` unions, `TypedDict`, and `dataclasses`. `Optional[X]`
is banned — write `X | None` instead. Type annotations MUST be present on all
public functions and class attributes.

**Pydantic for All Data Boundaries**
Every API request/response, every configuration object, and every inter-service
message MUST be represented by a Pydantic model. Raw `dict` objects MUST NOT
cross module boundaries. This applies to LLM tool call arguments, event
payloads, and database row mappings alike.

**Async by Default**
All I/O-bound operations MUST use `async/await`. Performing blocking calls
inside an async context (e.g., `requests.get`, synchronous file reads without
`asyncio.to_thread`) is not acceptable and MUST be caught in code review.

**No Business Logic in Route Handlers**
FastAPI route functions MUST only: validate input, delegate to a service or
graph function, and return output. Business logic, data transformations, and
orchestration MUST live in `graphs/`, `tools/`, or dedicated service modules.

**Fail Loudly on Startup**
If a required environment variable is missing or a downstream critical service
is unreachable at startup, the process MUST exit immediately with a clear,
human-readable error message. Silent degradation, lazy initialisation of
critical dependencies, and swallowing startup exceptions are prohibited.

## III. Testing Standards

**Every Agent Graph Has an Offline Unit Test**
Every `StateGraph` implementation in `agent/graphs/` MUST have a corresponding
unit test that runs without network access. Tests MUST use mocked LLM responses.
Calling real model provider APIs inside the test suite is prohibited.

**Integration Tests Are Opt-In**
Integration tests require a running stack and MUST be skipped in the default
`pytest` run. They are activated via the `TEST_INTEGRATION=true` environment
variable. CI MUST run unit tests unconditionally and integration tests as a
separate optional job.

**Evals Are Separate from Tests**
LLM quality evaluation (accuracy, faithfulness, relevance) lives exclusively
in `evals/` and is executed as a dedicated CI step. Eval code MUST NOT appear
in `tests/` and MUST NOT be part of `pytest` collection.

**Test File Mirrors Source File**
For every source file there MUST be a corresponding test file at the mirrored
path under `tests/`. Example: `agent/graphs/tool_agent.py` →
`tests/graphs/test_tool_agent.py`. Deviations require explicit justification in
the plan.

## IV. Observability Standards

**Every Agent Execution Produces a Langfuse Trace**
No LLM call may occur outside a Langfuse trace context. Trace IDs MUST be
propagated through the call stack and returned in all API responses that trigger
agent execution. Uninstrumented LLM calls are treated as defects.

**Structured Logging Everywhere**
All production code MUST use `structlog` or Python's standard `logging` module
configured with a JSON formatter. `print()` statements in production code are
prohibited and MUST fail linting/CI checks.

**Health Endpoints Are Honest**
`GET /health` returns HTTP 200 only when all critical dependencies (Redis,
Postgres, Qdrant) are confirmed reachable. Any unreachable dependency MUST
cause the endpoint to return 503 with a structured body identifying the failing
dependency. Endpoints that return 200 unconditionally are a defect.

## V. Security

**Secrets Never in Code or Logs**
API keys, passwords, tokens, and credentials MUST only be sourced from
environment variables. They MUST NEVER appear in source code, committed files,
or log output. Log sanitization MUST strip any value matching patterns for
known secret formats before emission.

**API Authentication on Every External Endpoint**
All externally accessible routes, except `GET /health`, MUST require
authentication via the `X-API-Key` header validated against `AGENT_API_KEY`.
Unauthenticated requests to protected routes MUST return 401. This is enforced
via a shared FastAPI dependency and MUST NOT be re-implemented per route.

**Tool Sandboxing Is Not Optional**
Any tool that executes external code, runs shell commands, or performs
filesystem writes MUST run in an isolated context — either a subprocess with
restricted OS permissions or an E2B cloud sandbox. Direct execution in the main
process environment is prohibited for such tools.

## VI. LLM Interaction

**Agents Always Talk to LiteLLM, Never Directly to Providers**
No agent or service code may import or instantiate the `anthropic`, `openai`,
`cohere`, or any other provider SDK directly. All LLM calls MUST go through the
OpenAI-compatible client pointed at `LITELLM_BASE_URL`. This ensures provider
portability and centralised rate-limit / cost management.

**Model Names Are Always Aliases**
Agent code MUST reference models by logical aliases (`default`, `fast`,
`embedding`, `vision`). Hardcoded provider model strings (e.g.,
`claude-sonnet-4-5`, `gpt-4o`) are banned from agent code. Alias-to-model
mapping is configured in the LiteLLM config and resolved at runtime.

**Prompts Are Versioned Assets**
System prompts MUST live in `agent/prompts/` as `.md` files with meaningful
names. Inline prompt strings in Python source are prohibited. All prompt files
MUST be loaded at service startup so missing prompts cause immediate startup
failure (see §II Fail Loudly on Startup).

## VII. Extensibility

**New Agents Follow the LangGraph Pattern**
Every agent MUST be implemented as a compiled `StateGraph` residing in
`agent/graphs/`. Ad-hoc chain implementations, custom execution loops, or
direct LLM call sequences outside this pattern are prohibited without a formal
architecture decision record (ADR).

**Tools Are MCP-Compatible**
All tool definitions MUST conform to the MCP (Model Context Protocol) schema.
This ensures they can be exposed as an MCP server in the future without
requiring refactoring. Tool input schemas MUST be defined as JSON Schema objects
compatible with the MCP `tools/list` contract.

**Multi-Tenancy via Namespace, Not Instance**
Client isolation MUST be achieved using key prefixes: Redis keys and Qdrant
collection names MUST follow the `{client_id}:*` pattern. Spinning up separate
service instances for standard multi-tenant isolation is prohibited. Dedicated
instances are reserved exclusively for enterprise contracts with documented
approval.

**Infrastructure as Code**
All infrastructure — cloud resources, Kubernetes manifests, DNS records, secret
store configuration, and CI/CD pipelines — MUST be defined and managed as code
using IaC tooling (Terraform, Pulumi, or Helm). Manual provisioning of any
infrastructure resource is prohibited. IaC definitions live in the `infra/`
directory and are subject to the same code-review process as application code.

## Governance

This constitution supersedes all other documented or informal practices. It
applies to all contributors, automated agents, and CI/CD pipelines acting on
this repository.

**Amendment Procedure**
Amendments require: (1) a written proposal describing the change and rationale,
(2) approval from the project lead or a designated RFC process
(TODO(GOVERNANCE_APPROVAL): define approvers), (3) an updated version line
following the semantic versioning policy below, and (4) a migration plan for
any in-flight work affected by the change.

**Versioning Policy**
- `MAJOR` bump: Backward-incompatible governance change — a principle removed,
  fundamentally redefined, or a mandatory practice made optional.
- `MINOR` bump: New principle or section added, or materially expanded guidance
  that introduces new obligations.
- `PATCH` bump: Clarifications, wording improvements, typo fixes, and
  non-semantic refinements.

**Compliance Review**
Every pull request MUST include a Constitution Check (see `plan-template.md`)
confirming that the change complies with all applicable principles. Violations
require explicit justification documented in the PR description and logged in
the Complexity Tracking table of the relevant plan.

**Version**: 1.0.0 | **Ratified**: 2026-03-13 | **Last Amended**: 2026-03-13
