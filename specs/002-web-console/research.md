# Research: Web Console API/CLI Parity

## Decision 1: Frontend stack and architecture
- Decision: Build the console as a dedicated React + TypeScript package using Tailwind CSS and shadcn/ui components.
- Rationale: This matches user direction, supports fast composable UI development, and gives a predictable design system for complex operator workflows.
- Alternatives considered: Plain React with custom CSS (rejected for slower consistency), heavyweight meta-framework SSR setup (rejected as unnecessary for internal operator console v1).

## Decision 2: API interaction model
- Decision: Use a hybrid model: backend proxy mode in production and direct API-key mode in local/dev.
- Rationale: Aligns with clarified requirement FR-015 and minimizes production key exposure while preserving local developer ergonomics.
- Alternatives considered: Proxy-only in all environments (rejected due to higher local setup friction), direct-only from browser (rejected due to production security concerns).

## Decision 3: Authentication posture for v1
- Decision: Keep network-trust model initially with no per-user login in the console.
- Rationale: Explicitly selected in clarifications (FR-017) and acceptable for private-network initial rollout.
- Alternatives considered: Full SSO/OIDC login (rejected for v1 timeline), static shared password gate (rejected as weak incremental security with management overhead).

## Decision 4: Async job UX strategy
- Decision: Poll every 2 seconds with 5-minute default timeout and visible progress states.
- Rationale: Directly matches FR-019 and avoids adding a websocket/SSE dependency in the first release.
- Alternatives considered: Websocket push updates (rejected due to extra infra complexity), slower polling interval (rejected for reduced operator responsiveness).

## Decision 5: Profile credential persistence
- Decision: Persist API keys in local profile storage, mask by default, and require explicit reveal action.
- Rationale: Matches FR-021 while improving operator usability across sessions.
- Alternatives considered: Session-only key storage (rejected for repeated re-entry friction), plaintext always visible (rejected for shoulder-surfing risk).

## Decision 6: API contract approach for UI
- Decision: Reuse existing backend OpenAPI routes and codify web-console request/response expectations as feature contracts.
- Rationale: Keeps parity with existing API/CLI behavior and provides a clear implementation/testing baseline for frontend.
- Alternatives considered: New backend-for-frontend custom endpoints (rejected as unnecessary duplication for v1 parity scope).
