# Implementation Plan: Web Console API/CLI Parity

**Branch**: `002-web-console` | **Date**: 2026-04-03 | **Spec**: `/specs/002-web-console/spec.md`
**Input**: Feature specification from `/specs/002-web-console/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Build an operator-focused web console that mirrors API/CLI capabilities (health, agents, run, replay, session chat, async jobs, approvals) while using a hybrid security model: backend proxy in production and direct API-key mode for local/dev. The frontend will be implemented as a React web app styled with Tailwind CSS and shadcn/ui components, with profile persistence, resilient error handling, and polling-based async UX.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: TypeScript 5.x, React 18.x  
**Primary Dependencies**: React, Vite, Tailwind CSS, shadcn/ui, fetch API  
**Storage**: Browser local storage for profile persistence; backend remains source of truth for domain data  
**Testing**: Vitest + React Testing Library (frontend), existing pytest suites for backend contract checks  
**Target Platform**: Modern desktop browsers on private network/VPN, responsive down to tablet width
**Project Type**: Web application package in monorepo (`packages/web-console`)  
**Performance Goals**: Initial view interactive in <2s on local network; standard action feedback in <2s plus backend latency; polling loop at 2s interval default  
**Constraints**: Network-trust auth posture for initial release, no dedicated audit trail, API-key masking by default, no real-time push dependency  
**Scale/Scope**: Single operator session at a time; parity for all currently exposed API/CLI operations listed in spec (FR-014)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Architecture (PASS)**: Console will be packaged inside existing monorepo and run with local/container stack; no managed-cloud hard dependency.
- **II. Code Quality (PASS)**: TypeScript strict mode and explicit API typing will be enforced; no business logic inside backend routes is added by this feature.
- **III. Testing Standards (PASS)**: New frontend tests added under package tests; backend integration validations remain opt-in and unchanged.
- **IV. Observability Standards (PASS with note)**: No new LLM execution path added; console surfaces trace IDs returned by backend and preserves visibility.
- **V. Security (PASS with scoped exception acknowledged in spec)**: Initial release intentionally uses network trust + no per-user auth, explicitly documented in FR-017/FR-018 and assumptions.
- **VI. LLM Interaction (PASS)**: Console does not bypass LiteLLM architecture; it uses existing backend/API contracts only.
- **VII. Extensibility (PASS)**: Feature extends UI surface without altering agent graph pattern; README update required alongside implementation.

**Post-design re-check**: No additional constitution violations introduced by chosen architecture; all scoped constraints remain explicit and accepted.

## Project Structure

### Documentation (this feature)

```text
specs/002-web-console/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
packages/
├── tenant-cli/
└── web-console/
    ├── src/
    │   ├── app/
    │   ├── components/
    │   │   ├── ui/               # shadcn/ui-generated primitives
    │   │   ├── profile/
    │   │   ├── agents/
    │   │   ├── run/
    │   │   ├── session/
    │   │   ├── jobs/
    │   │   └── approvals/
    │   ├── lib/
    │   │   ├── api-client.ts
    │   │   ├── profile-store.ts
    │   │   └── formatters.ts
    │   ├── styles/
    │   │   └── globals.css       # tailwind entry
    │   └── main.tsx
    ├── tests/
    ├── package.json
    ├── tsconfig.json
    └── vite.config.ts

tests/
├── cli/
├── integration/
└── routes/
```

**Structure Decision**: Use a new monorepo package `packages/web-console` (web-application pattern) to keep UI delivery isolated from backend and CLI while preserving shared repository workflows.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
