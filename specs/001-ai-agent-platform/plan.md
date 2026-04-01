# Implementation Plan: Tenant-Facing CLI for 2brain Platform

**Branch**: `001-ai-agent-platform` | **Date**: 2026-04-01 | **Spec**: [`spec.md`](./spec.md)
**Input**: Feature specification from `/specs/001-ai-agent-platform/spec.md`

## Summary

Extend the existing 2brain platform with a tenant-facing CLI that exposes the same authenticated API operations already defined in the spec: synchronous runs, session-based conversations, async job submission/status polling, and approval review/decision flows. The implementation will be **React Ink / TypeScript first**, using a Node-based `2brain` CLI as the primary interface while still supporting stable `--json` output for scripting and automation. The FastAPI service remains the single authority for auth, tenant isolation, policy checks, and execution orchestration.

A notable implementation dependency is that `api/routes/approvals.py` is currently only a stub, while `spec.md` and `contracts/agent-api.yaml` already define the approval endpoints. The CLI plan therefore includes closing that API gap rather than bypassing the public contract.

## Technical Context

**Language/Version**: Python 3.12+ for the backend; TypeScript + Node.js 22 for the primary Ink-based CLI  
**Primary Dependencies**: FastAPI, Pydantic, structlog, existing SQLAlchemy/Redis/RQ stack on the backend; React + Ink, TypeScript, and a Node HTTP client for the CLI  
**Storage**: PostgreSQL, Redis, Qdrant, Langfuse; CLI itself remains stateless except for a local profile/config file  
**Testing**: `pytest`, `pytest-asyncio`, FastAPI contract/integration tests; `ink-testing-library` or Vitest for the Ink CLI layer  
**Target Platform**: Linux and macOS terminals, plus non-interactive CI shells  
**Project Type**: Self-hosted Python web platform with a companion Ink/Node tenant CLI  
**Performance Goals**: Human-readable CLI commands should start in under 1 second locally; polling/refresh defaults should keep async and approval state visibly current within ~2 seconds; CLI must add negligible overhead beyond current API latency  
**Constraints**: CLI must use the public HTTP API only; no auth bypasses or direct DB access; non-interactive mode must support JSON output for scripting; no streaming required in this version  
**Scale/Scope**: Cover all FR-043/FR-044 tenant-facing flows for a single-host deployment, supporting multiple tenant operators and concurrent long-running jobs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- ✅ **Cloud Agnostic First**: the CLI is local client code only and adds no managed-cloud dependency.
- ✅ **Single Compose File as Source of Truth**: no new always-on infrastructure is introduced; backend services remain in the existing compose stack.
- ✅ **Explicit over Implicit**: CLI configuration will be documented and resolved explicitly from env vars and/or a local profile file.
- ✅ **Pydantic for All Data Boundaries**: CLI request/response payloads will reuse or mirror the existing Pydantic API models.
- ✅ **Async by Default**: network I/O in the CLI will use async HTTP clients and non-blocking polling loops.
- ✅ **API Authentication on Every External Endpoint**: the CLI will send `X-API-Key` and consume the same public endpoints as any tenant integration.
- ✅ **README Is a Living Task Ledger**: README and `quickstart.md` are updated as part of this planning iteration.
- ⚠️ **Complexity note — extra Node runtime**: React Ink requires a Node/TypeScript package for the tenant CLI. This is acceptable because the product direction is explicitly Ink-first, and `--json` mode still covers automation needs.

**Gate Result**: **PASS** — no blocking constitution violations; one justified complexity note is tracked below.

## Project Structure

### Documentation (this feature)

```text
specs/001-ai-agent-platform/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── agent-api.yaml
│   ├── cli-commands.md
│   └── litellm-aliases.md
└── tasks.md
```

### Source Code (repository root)

```text
api/
├── models/
├── routes/
└── deps.py

agent/
├── service.py
├── session_store.py
├── policy.py
└── graphs/

worker/
└── queue.py

packages/tenant-cli/
├── package.json
├── tsconfig.json
├── src/
│   ├── cli.tsx          # `2brain` Ink entrypoint
│   ├── index.ts         # package/bin export
│   ├── config.ts        # profile + env resolution
│   ├── output.ts        # json/plain output selection
│   ├── api/
│   │   └── client.ts    # shared HTTP wrapper around the public API
│   ├── commands/
│   │   ├── run.tsx
│   │   ├── chat.tsx
│   │   ├── jobs.tsx
│   │   ├── approvals.tsx
│   │   └── config.tsx
│   └── ui/
└── tests/

tests/
├── routes/
├── integration/
└── cli/
```

**Structure Decision**: Keep the authoritative platform runtime in the existing Python services, and build the tenant CLI directly as an **Ink/Node package** in-repo. The CLI itself is the interactive experience, while `--json` mode preserves scriptability without maintaining a second Python command surface.

## Complexity Tracking

| Violation / Complexity | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Node/TypeScript runtime for the tenant CLI | Needed because the CLI is intentionally built with React Ink rather than Python | A pure Python CLI was rejected by product direction; `--json` mode covers scripting without requiring a second implementation |
