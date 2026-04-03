# Tasks: Web Console API/CLI Parity

**Input**: Design documents from `/specs/002-web-console/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize the web-console package and baseline toolchain.

- [ ] T001 Create package scaffold and npm scripts in `packages/web-console/package.json`
- [ ] T002 [P] Configure TypeScript and Vite for React app in `packages/web-console/tsconfig.json` and `packages/web-console/vite.config.ts`
- [ ] T003 [P] Configure Tailwind CSS and PostCSS in `packages/web-console/tailwind.config.ts` and `packages/web-console/postcss.config.js`
- [ ] T004 [P] Initialize shadcn/ui settings and base design tokens in `packages/web-console/components.json` and `packages/web-console/src/styles/globals.css`
- [ ] T005 Build initial app bootstrap and root mount in `packages/web-console/src/main.tsx` and `packages/web-console/src/app/App.tsx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core UI/runtime building blocks that all user stories depend on.

**⚠️ CRITICAL**: No user story implementation starts before this phase completes.

- [ ] T006 Define shared API and domain types in `packages/web-console/src/lib/types.ts`
- [ ] T007 Implement profile storage repository with migration/backup behavior in `packages/web-console/src/lib/profile-store.ts`
- [ ] T008 [P] Implement hybrid API client (proxy/direct modes) in `packages/web-console/src/lib/api-client.ts`
- [ ] T009 [P] Implement normalized error mapper and trace-id extraction in `packages/web-console/src/lib/error-normalizer.ts`
- [ ] T010 [P] Create reusable async request state hook in `packages/web-console/src/hooks/useRequestState.ts`
- [ ] T011 [P] Create shared JSON response viewer component in `packages/web-console/src/components/ui/json-viewer.tsx`
- [ ] T012 Build global app state provider for active profile and operation history in `packages/web-console/src/app/AppStateProvider.tsx`
- [ ] T013 Implement shell layout with module navigation and persistent result pane in `packages/web-console/src/app/AppLayout.tsx`

**Checkpoint**: Foundation complete, user stories can now be implemented.

---

## Phase 3: User Story 1 - Configure and Connect a Tenant Profile (Priority: P1) 🎯 MVP

**Goal**: Let operators create/select persisted profiles and validate connectivity.

**Independent Test**: Create profile, switch active profile, run health check, and see success/error feedback without losing previous results.

### Implementation for User Story 1

- [ ] T014 [P] [US1] Define ConsoleProfile form schema and validators in `packages/web-console/src/components/profile/profile-validation.ts`
- [ ] T015 [US1] Implement profile CRUD panel (create/edit/delete/select) in `packages/web-console/src/components/profile/ProfilePanel.tsx`
- [ ] T016 [US1] Implement masked API key input with explicit reveal behavior in `packages/web-console/src/components/profile/ApiKeyField.tsx`
- [ ] T017 [US1] Implement active-profile summary and auth-posture warning banner in `packages/web-console/src/components/profile/ActiveProfileBanner.tsx`
- [ ] T018 [US1] Wire profile state actions to local storage repository in `packages/web-console/src/app/AppStateProvider.tsx`
- [ ] T019 [US1] Implement health check action and dependency status rendering in `packages/web-console/src/components/health/HealthPanel.tsx`
- [ ] T020 [US1] Preserve last successful operation result on subsequent failure in `packages/web-console/src/app/operation-history.ts`

**Checkpoint**: US1 delivers a working MVP for connection setup and verification.

---

## Phase 4: User Story 2 - Execute Agent Workflows from the Console (Priority: P2)

**Goal**: Run day-to-day synchronous operations (agents, run, replay, session chat) from the UI.

**Independent Test**: List/create agents, run sync execution, send multi-turn session chat, and replay by trace ID entirely from console.

### Implementation for User Story 2

- [ ] T021 [P] [US2] Implement agents list/create API service wrappers in `packages/web-console/src/lib/services/agents-service.ts`
- [ ] T022 [US2] Implement Agents panel with list/create forms in `packages/web-console/src/components/agents/AgentsPanel.tsx`
- [ ] T023 [P] [US2] Implement run execution API service in `packages/web-console/src/lib/services/run-service.ts`
- [ ] T024 [US2] Implement Run panel with structured response rendering in `packages/web-console/src/components/run/RunPanel.tsx`
- [ ] T025 [P] [US2] Implement replay API service in `packages/web-console/src/lib/services/replay-service.ts`
- [ ] T026 [US2] Implement Replay panel with trace-id driven rerun flow in `packages/web-console/src/components/run/ReplayPanel.tsx`
- [ ] T027 [P] [US2] Implement session message API service in `packages/web-console/src/lib/services/session-service.ts`
- [ ] T028 [US2] Implement Session chat panel with chronological transcript rendering in `packages/web-console/src/components/session/SessionPanel.tsx`
- [ ] T029 [US2] Add operation-level loading/error states and retry actions for agents/run/replay/session in `packages/web-console/src/components/shared/OperationState.tsx`

**Checkpoint**: US2 enables complete synchronous operator workflows in the web console.

---

## Phase 5: User Story 3 - Monitor Jobs and Resolve HITL Approvals (Priority: P3)

**Goal**: Operate async jobs and human approval flows without CLI.

**Independent Test**: Submit async job, watch status updates with 2s polling/5m timeout, open approval details, and send approve/reject decision.

### Implementation for User Story 3

- [ ] T030 [P] [US3] Implement jobs submit/status API service wrappers in `packages/web-console/src/lib/services/jobs-service.ts`
- [ ] T031 [P] [US3] Implement polling engine with timeout/retry/backoff policy in `packages/web-console/src/lib/polling/job-poller.ts`
- [ ] T032 [US3] Implement Jobs panel with submit/status/watch controls in `packages/web-console/src/components/jobs/JobsPanel.tsx`
- [ ] T033 [P] [US3] Implement approvals API service wrappers in `packages/web-console/src/lib/services/approvals-service.ts`
- [ ] T034 [US3] Implement Approval details panel for pending approvals in `packages/web-console/src/components/approvals/ApprovalDetailsPanel.tsx`
- [ ] T035 [US3] Implement approval decision form (approve/reject, reviewer, reason) in `packages/web-console/src/components/approvals/ApprovalDecisionForm.tsx`
- [ ] T036 [US3] Link interrupted job snapshots to approval fetch flow in `packages/web-console/src/components/jobs/JobApprovalLink.tsx`

**Checkpoint**: US3 completes async operations and HITL decision handling in UI.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final hardening and documentation across all stories.

- [ ] T037 [P] Add responsive layout and accessibility refinements across panels in `packages/web-console/src/app/AppLayout.tsx`
- [ ] T038 [P] Add consistent empty/loading/error states and toasts in `packages/web-console/src/components/shared/feedback.tsx`
- [ ] T039 [P] Add unit tests for profile storage and API client mode selection in `packages/web-console/tests/lib/profile-store.test.ts` and `packages/web-console/tests/lib/api-client.test.ts`
- [ ] T040 [P] Add component tests for core panel flows in `packages/web-console/tests/components/profile-health.test.tsx` and `packages/web-console/tests/components/workflows.test.tsx`
- [ ] T041 Update setup, security posture, and limitations docs in `README.md` and `packages/web-console/README.md`
- [ ] T042 Validate quickstart end-to-end and record final checklist notes in `specs/002-web-console/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: starts immediately.
- **Phase 2 (Foundational)**: depends on Phase 1 completion and blocks all user stories.
- **Phase 3 (US1)**: depends on Phase 2; recommended MVP first release.
- **Phase 4 (US2)**: depends on Phase 2 and can run in parallel with US3 if needed.
- **Phase 5 (US3)**: depends on Phase 2 and can run in parallel with US2 if needed.
- **Phase 6 (Polish)**: depends on completion of desired user stories.

### User Story Dependencies

- **US1 (P1)**: no dependency on other user stories after foundational phase.
- **US2 (P2)**: no hard dependency on US1, but uses selected active profile from shared foundation.
- **US3 (P3)**: no hard dependency on US2; uses shared API client/state and can be developed independently.

### Within Each User Story

- Form/schema and service wrappers before panel integration.
- Panel implementation before cross-panel linking.
- Story checkpoint validation before moving to next story.

---

## Parallel Opportunities

- **Setup**: T002, T003, T004 can run in parallel after T001.
- **Foundational**: T008, T009, T010, T011 can run in parallel after T006/T007.
- **US1**: T014 can run parallel to T019; T015 and T016 can progress together once validation exists.
- **US2**: T021, T023, T025, T027 can run in parallel as separate service modules.
- **US3**: T030, T031, T033 can run in parallel before panel wiring.
- **Polish**: T037, T038, T039, T040 can run in parallel across frontend contributors.

---

## Parallel Example: User Story 2

```bash
# Parallel backend-client tasks
Task: T021 Implement agents service wrappers in packages/web-console/src/lib/services/agents-service.ts
Task: T023 Implement run service in packages/web-console/src/lib/services/run-service.ts
Task: T025 Implement replay service in packages/web-console/src/lib/services/replay-service.ts
Task: T027 Implement session service in packages/web-console/src/lib/services/session-service.ts

# Parallel UI tasks after services are merged
Task: T022 Implement Agents panel in packages/web-console/src/components/agents/AgentsPanel.tsx
Task: T024 Implement Run panel in packages/web-console/src/components/run/RunPanel.tsx
Task: T026 Implement Replay panel in packages/web-console/src/components/run/ReplayPanel.tsx
Task: T028 Implement Session panel in packages/web-console/src/components/session/SessionPanel.tsx
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1).
3. Validate profile persistence, active switching, and health check behavior.
4. Demo/deploy MVP.

### Incremental Delivery

1. Deliver MVP with US1.
2. Add US2 and validate synchronous workflows.
3. Add US3 and validate async + HITL workflows.
4. Run polish tasks and update docs.

### Suggested MVP Scope

- **MVP**: Through T020 (end of US1).
- **Release Candidate**: Through T036 (all user stories complete).
- **Production-ready hardening**: Through T042.
