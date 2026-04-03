# Feature Specification: Web Console API/CLI Parity

**Feature Branch**: `002-web-console`  
**Created**: 2026-04-03  
**Status**: Draft  
**Input**: User description: "webconsole - crea una web console che replichi le feature esposte via api e cli"

## Clarifications

### Session 2026-04-03

- Q: Which security model should the web console use for API calls? -> A: Hybrid model: backend proxy in production, direct API-key mode only for local/dev.
- Q: Which operator authentication model should be used initially for the production console? -> A: Network-only trust model for now (private network/VPN), without per-user console authentication in initial release.
- Q: What should be the default async job polling cadence and timeout in the console watcher? -> A: Poll every 2 seconds with default timeout of 5 minutes.
- Q: Should the first release include a dedicated console audit trail? -> A: No dedicated audit trail in this release.
- Q: How should API keys be handled in persisted console profiles? -> A: Persist API keys, mask by default in UI, and require explicit reveal action per session.

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Configure and Connect a Tenant Profile (Priority: P1)

As a tenant operator, I can configure one or more API profiles in the web console (base URL + API key), select an active profile, and validate connectivity so I can operate the platform without using terminal commands.

**Why this priority**: Every other capability depends on a valid profile and authenticated API calls.

**Independent Test**: Configure a profile in the UI, switch to it, execute a health check and at least one authenticated call, and receive a successful response or a clear error.

**Acceptance Scenarios**:

1. **Given** no saved profile exists, **When** the user creates one with base URL and API key, **Then** the profile is saved and reusable in future sessions.
2. **Given** multiple profiles are available, **When** the user selects a different active profile, **Then** all subsequent actions use that profile without re-entering credentials.
3. **Given** an invalid API key, **When** the user runs a console action, **Then** the console shows a clear unauthorized error without crashing.

---

### User Story 2 - Execute Agent Workflows from the Console (Priority: P2)

As a tenant operator, I can run synchronous calls, replay traces, run session conversations, and manage agents directly from the web console so I can perform day-to-day operations from a single visual interface.

**Why this priority**: This is the core productivity surface and replaces repeated manual API/CLI invocations.

**Independent Test**: From the console only, successfully list/create agents, run a sync call, start a session conversation, and execute a replay using a known trace ID.

**Acceptance Scenarios**:

1. **Given** a valid agent ID and input, **When** the user runs a synchronous execution, **Then** the console displays output, status, trace ID, and job ID.
2. **Given** a session ID, **When** the user sends multiple chat turns, **Then** the conversation view appends each user/assistant exchange in order.
3. **Given** a source trace ID, **When** the user triggers replay, **Then** the replay response is shown with its own output and trace context.
4. **Given** agent management access, **When** the user lists or creates agents, **Then** the console reflects updated agent inventory.

---

### User Story 3 - Monitor Jobs and Resolve HITL Approvals (Priority: P3)

As a tenant operator, I can submit async jobs, track status, inspect pending approvals, and approve/reject requests from the web console so background flows and safety gates are fully operable without CLI.

**Why this priority**: Async and HITL handling are critical for production operations and incident response.

**Independent Test**: Submit an async job, monitor until interrupted/completed, fetch approval details when present, and submit approve/reject decisions from the console.

**Acceptance Scenarios**:

1. **Given** a valid async request, **When** the user submits a job, **Then** the job ID is displayed and can be queried for status updates.
2. **Given** a job enters interrupted state with a pending approval ID, **When** the user opens approval details, **Then** tool name, args, timeout, and status are visible.
3. **Given** a pending approval request, **When** the user approves or rejects with reviewer identity, **Then** the decision is recorded and the updated approval status is shown.

---

### Edge Cases

- What happens when a saved profile has an unreachable base URL or malformed API prefix?
- How does the console behave when API returns non-JSON or unexpected payload structures?
- What happens when users trigger concurrent actions (e.g., job polling + approval decision) on the same job?
- How does chat history rendering handle long responses and rapid multi-turn input?
- What happens when an approval decision is attempted on a request already decided or timed out?
- How does replay behave when the source trace ID is missing or no longer available?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The web console MUST support creating, editing, deleting, and selecting named tenant profiles containing base URL and API key.
- **FR-002**: The web console MUST persist profiles and active profile selection across browser sessions on the same client.
- **FR-003**: The web console MUST expose a health check action and display dependency status from the health endpoint.
- **FR-004**: The web console MUST allow users to list and create agent definitions through the same public API contract used by CLI.
- **FR-005**: The web console MUST support synchronous run execution with optional session ID and show full structured response fields.
- **FR-006**: The web console MUST support trace replay by accepting source trace ID, agent ID, and replay input.
- **FR-007**: The web console MUST support session chat interactions where each turn is sent using the selected session ID and rendered in chronological order.
- **FR-008**: The web console MUST support async job submit, status fetch, and watch/poll behavior until terminal states.
- **FR-009**: When a job exposes a pending approval ID, the web console MUST allow opening approval details and display relevant context.
- **FR-010**: The web console MUST allow approve/reject decisions with reviewer identity and optional reason.
- **FR-011**: The web console MUST display actionable error states for authentication errors, validation errors, conflicts, and service unavailability.
- **FR-012**: The web console MUST prevent loss of already displayed operation results when a subsequent operation fails.
- **FR-013**: The web console MUST provide a response viewer that is readable for both compact and nested payloads.
- **FR-014**: The web console MUST replicate capability coverage currently available through API/CLI for: health, agents, run, replay, session conversation, jobs, and approvals.
- **FR-015**: In production environments, the web console MUST route API operations through a backend proxy service instead of exposing tenant API keys in browser requests.
- **FR-016**: In local/dev environments, the web console MAY call platform APIs directly using tenant API keys to support rapid setup and parity testing.
- **FR-017**: The initial production release MUST rely on private-network access controls (for example VPN/internal network boundaries) instead of implementing per-user console authentication.
- **FR-018**: The console MUST clearly indicate that the initial authentication posture is network-scoped and that stronger per-user authentication is out of scope for this release.
- **FR-019**: The async job watcher MUST poll status every 2 seconds by default and stop after a default timeout of 5 minutes unless user-configured otherwise.
- **FR-020**: The initial release MUST NOT require a dedicated console audit trail implementation; any existing platform-level logs may be used as-is.
- **FR-021**: Persisted profile API keys MUST be masked by default in the UI and revealed only after an explicit user action in the active session.

### Key Entities *(include if feature involves data)*

- **Console Profile**: A saved client-side configuration containing profile name, API base URL, API key, and active-selection state.
- **Operation Request**: A user-initiated action (run, replay, create agent, submit job, approval decision) with its form inputs.
- **Operation Result**: The structured API response plus timestamp and request context shown in the console output pane.
- **Session Transcript Entry**: A chronological message item (role + content + optional trace metadata) for web-based session chat.
- **Job Tracking Snapshot**: A point-in-time view of async job lifecycle state and related approval linkage.
- **Approval Decision Payload**: Reviewer action details (approved/rejected, reviewer ID, optional reason) submitted to the approval endpoint.

### Assumptions

- The web console is an operator-facing tool and supports direct client-side API-key profile storage only for local/dev usage.
- The backend remains the source of truth for authentication, tenancy, validation, and business rules.
- The initial release does not include per-user console authentication and depends on network perimeter controls for operator access.
- The initial release does not include a dedicated console audit trail.
- Persisted API keys are allowed in this release but must be hidden by default in the interface.
- Existing public service operations remain stable across the release window.
- Initial scope is single-tenant-at-a-time interaction via selected profile (no multi-profile concurrent sessions).
- Real-time push updates are not required; periodic refresh is acceptable for async job tracking.

### Dependencies

- Availability of the existing public API endpoints for health, agents, run, replay, jobs, and approvals.
- Existing tenancy and API-key authentication behavior.
- Availability of a production backend proxy path that enforces secure credential handling for web-console requests.
- Availability of controlled private network access (for example VPN/internal ingress restrictions) for production console exposure.
- Browser environment with JavaScript enabled and network access to API base URL.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new operator can configure a profile and execute the first successful synchronous run within 3 minutes.
- **SC-002**: 95% of standard console operations (list agents, run, submit job, get approval) return visible results or explicit actionable errors within 2 seconds plus backend latency.
- **SC-003**: In acceptance testing, users complete end-to-end async flow (submit job → status → approval decision when needed) without CLI in at least 9 of 10 runs.
- **SC-004**: At least 90% of API/CLI functional coverage surfaces are available as equivalent actions in the web console at release time.
- **SC-005**: During usability validation, at least 85% of participants can locate and perform run, jobs, and approvals actions without external guidance.
