# Data Model: Web Console

## Entity: ConsoleProfile
- Purpose: Named connection profile used by operators to target API endpoints.
- Fields:
- `id` (string, UUID-like)
- `name` (string, required, unique in local store)
- `baseUrl` (string, required, valid URL)
- `apiKey` (string, required, stored locally, masked in UI by default)
- `defaultAgentId` (string, optional)
- `mode` (enum: `proxy`, `direct`)
- `createdAt` (ISO datetime)
- `updatedAt` (ISO datetime)
- Validation:
- `name` length 1..64
- `baseUrl` must be `http` or `https`
- `apiKey` non-empty when mode is `direct`
- Relationships:
- One profile can be used by many runs/chats/jobs in session scope.

## Entity: AgentSummary
- Purpose: Lightweight representation of an agent in list and selector views.
- Fields:
- `agentId` (string)
- `name` (string)
- `description` (string, optional)
- `createdAt` (ISO datetime, optional)
- Validation:
- `agentId` required and unique in a loaded list.

## Entity: AgentCreateInput
- Purpose: Payload for creating agent definitions from the console.
- Fields:
- `name` (string, required)
- `systemPrompt` (string, optional)
- `model` (string, optional)
- `tools` (array of string, optional)
- Validation:
- `name` required, non-empty
- `tools` entries unique when provided.

## Entity: RunRequest
- Purpose: Input for starting a run operation.
- Fields:
- `agentId` (string, required)
- `input` (string or structured JSON, required)
- `sessionId` (string, optional)
- `metadata` (object, optional)
- Validation:
- `agentId` required
- `input` required.

## Entity: RunResult
- Purpose: Immediate run response rendered in run panel.
- Fields:
- `runId` (string)
- `status` (enum: `queued`, `running`, `succeeded`, `failed`)
- `output` (string or JSON, optional)
- `error` (object, optional)
- `traceId` (string, optional)
- State transitions:
- `queued -> running -> succeeded|failed`

## Entity: ReplayRequest
- Purpose: Input for rerunning prior run/session with modified prompt or params.
- Fields:
- `sourceRunId` (string, required)
- `overrideInput` (string or JSON, optional)
- `overrideAgentId` (string, optional)

## Entity: SessionMessage
- Purpose: Message item in chat/session transcript.
- Fields:
- `messageId` (string)
- `sessionId` (string)
- `role` (enum: `user`, `assistant`, `system`, `tool`)
- `content` (string)
- `createdAt` (ISO datetime)
- Validation:
- `content` required except tool-metadata-only messages.

## Entity: JobRequest
- Purpose: Input for asynchronous job submission.
- Fields:
- `jobType` (string, required)
- `payload` (object, required)
- `priority` (enum: `low`, `normal`, `high`, optional)

## Entity: JobStatus
- Purpose: Status object used by polling view.
- Fields:
- `jobId` (string)
- `status` (enum: `queued`, `running`, `completed`, `failed`, `cancelled`)
- `progress` (number 0..100, optional)
- `result` (object, optional)
- `error` (object, optional)
- `updatedAt` (ISO datetime)
- State transitions:
- `queued -> running -> completed|failed|cancelled`

## Entity: ApprovalItem
- Purpose: Approval request surfaced to operator.
- Fields:
- `approvalId` (string)
- `status` (enum: `pending`, `approved`, `rejected`)
- `reason` (string, optional)
- `requestedAt` (ISO datetime)
- `resolvedAt` (ISO datetime, optional)
- `context` (object, optional)
- State transitions:
- `pending -> approved|rejected`

## Entity: ApiErrorView
- Purpose: Normalized error envelope rendered consistently in UI.
- Fields:
- `code` (string)
- `message` (string)
- `details` (object, optional)
- `traceId` (string, optional)
- Validation:
- `message` always required for user-visible failures.
