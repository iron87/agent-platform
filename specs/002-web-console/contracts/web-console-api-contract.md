# Web Console API Contract

## Scope
This contract defines how the web console consumes existing platform endpoints to guarantee API/CLI parity for v1.

## Transport
- Protocol: HTTPS (HTTP allowed only for localhost development)
- Content type: `application/json`
- Timeout baseline: 30s request timeout for non-polling operations

## Client Modes

### Mode: `proxy` (production default)
- Browser calls backend proxy endpoints.
- Browser never sends provider keys directly to third-party model endpoints.
- Auth and header forwarding are controlled by backend.

### Mode: `direct` (local/dev)
- Browser calls API base URL from selected profile.
- Browser includes API key from selected profile.
- Required header: `Authorization: Bearer <apiKey>` unless backend profile specifies alternate header.

## Functional Endpoint Groups

### Health
- `GET /health`
- Success contract: JSON object with service status and dependency indicators.

### Agents
- `GET /agents`
- `POST /agents`
- Create request must include required fields per backend schema.

### Run / Replay
- `POST /run`
- `POST /run/replay` (or equivalent replay endpoint exposed by API)
- Response includes operation status and output/error payload.

### Session Chat
- `POST /sessions/{session_id}/messages` (or equivalent)
- Returns assistant/tool outputs for appended transcript rendering.

### Jobs
- `POST /jobs`
- `GET /jobs/{job_id}`
- Polling contract: 2s interval, stop on terminal state or 5-minute timeout.

### Approvals
- `GET /approvals/{approval_id}` and/or list endpoint
- `POST /approvals/{approval_id}/decision` with decision payload

## Error Contract
- Non-2xx responses must map to normalized UI error object:
- `code` (string)
- `message` (string)
- `details` (object, optional)
- `traceId` (string, optional)

## UI Behavior Contract
- Every request state must expose `idle|loading|success|error`.
- Error states must preserve user input where possible for retry.
- Trace ID, when available, must be visible to operators.

## Non-goals for v1
- Dedicated web-console audit trail storage.
- Per-user authentication/authorization layer.
- Real-time websocket/SSE subscription channel.
