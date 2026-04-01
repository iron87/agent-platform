# CLI Command Contract: Tenant-Facing 2brain CLI

**Date**: 2026-04-01 | **Spec**: [../spec.md](../spec.md)

This contract defines the planned tenant-facing CLI surface and maps each command to the existing public HTTP API. The CLI is a **client of the API**, not a privileged control path.

---

## Command Groups

| Command | Purpose | HTTP Mapping |
|---------|---------|--------------|
| `2brain run` | One-shot synchronous invocation | `POST /run` |
| `2brain session chat` | Stateful conversation using `session_id` | `POST /run` |
| `2brain jobs submit` | Async submission | `POST /jobs` |
| `2brain jobs status` | Inspect async status/result | `GET /jobs/{job_id}` |
| `2brain jobs wait` | Poll until completion | `GET /jobs/{job_id}` |
| `2brain approvals get` | Inspect pending approval details | `GET /approvals/{approval_id}` |
| `2brain approvals approve` | Approve a gated action | `POST /approvals/{approval_id}/decide` |
| `2brain approvals reject` | Reject a gated action | `POST /approvals/{approval_id}/decide` |
| `2brain config set` | Store local CLI profile | local only |
| `2brain ui` | Launch optional React Ink UI | same endpoints as above |

---

## Shared CLI Rules

1. All networked commands MUST accept either `--profile <name>` or explicit `--base-url` + `--api-key` flags.
2. All networked commands MUST send `X-API-Key` and `Content-Type: application/json` where applicable.
3. Every command MUST support `--json` for machine-readable output.
4. Human-friendly output is allowed by default, but must not change the underlying JSON schema returned with `--json`.
5. The CLI MUST never talk directly to Postgres, Redis, or internal worker queues.

---

## Command Details

### `2brain run`

```bash
2brain run --agent-id <uuid> --input "Hello" [--session-id demo] [--json]
```

**Request body**

```json
{
  "agent_id": "00000000-0000-0000-0000-000000000001",
  "input": "Hello",
  "session_id": null,
  "metadata": {}
}
```

**Expected response**: `RunResponse`

---

### `2brain jobs submit`

```bash
2brain jobs submit --agent-id <uuid> --input "Generate report"
```

**Expected response**

```json
{
  "job_id": "...",
  "status": "pending"
}
```

---

### `2brain jobs status`

```bash
2brain jobs status --job-id <uuid>
```

**Expected response**: `JobStatus`, including `pending_approval_id` when present.

---

### `2brain approvals approve|reject`

```bash
2brain approvals approve --approval-id <uuid> --reviewer-id alice@acme.com
2brain approvals reject --approval-id <uuid> --reviewer-id alice@acme.com --reason "Needs review"
```

**Decision payload**

```json
{
  "approved": true,
  "reason": null,
  "reviewer_id": "alice@acme.com"
}
```

**Expected response**: approval status plus the affected `job_id` and resulting execution state.

---

## Known Backend Dependency

The approval endpoints are already defined in `agent-api.yaml`, but `api/routes/approvals.py` is currently only a stub. Full CLI coverage for `approvals` depends on completing those routes to match the published contract.