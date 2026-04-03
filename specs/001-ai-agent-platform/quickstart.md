# Quickstart: 2brain AI Agent Platform

**Date**: 2026-03-14 | **Plan**: [plan.md](plan.md)

End-to-end walk-through for two audiences:
- **Agency engineers** — bootstrapping a new instance and verifying it works.
- **Tenant system integrators** — invoking an agent for the first time.

---

## Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| Linux host (or macOS + Docker Desktop) | Any | `uname -a` |
| Docker Engine | 24+ | `docker --version` |
| Docker Compose plugin | v2.20+ | `docker compose version` |
| Outbound internet access | — | pull images + reach LLM APIs |
| Anthropic or OpenAI API key | — | manual step only |

---

## Part 1 — Agency Engineer: Bootstrap a New Instance

### Step 1 — Clone the repository

```bash
git clone https://github.com/eiai-lab/2brain-platform.git
cd 2brain-platform
```

### Step 2 — Run the bootstrap script

```bash
bash infra/bootstrap.sh
```

**What the script does automatically:**
- **Preflight**: verifies `docker`, `openssl`, `curl` are available and the Docker daemon is running.
- **Idempotent secrets**: generates all internal secrets on first run; re-runs are safe — existing secrets are preserved. To force regeneration: `FORCE_REGENERATE=true bash infra/bootstrap.sh`.
- Writes a `.env` file at the repo root (never committed).
- Set `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY` in `.env` for external LLM access (optional when using a local model).
- Runs `docker compose --env-file .env up -d` to start all services in dependency order.
- Waits for each service to pass its healthcheck (up to 2 min per service).
- Prints a full summary including the generated `AGENT_API_KEY`.

Expected output on success:
```
==> Running preflight checks...
==> Preparing environment...
.env already exists — skipping creation (use FORCE_REGENERATE=true to reset secrets)
==> Starting services...
==> Waiting for dependencies to become healthy...
  [✓] qdrant
  [✓] langfuse
  [✓] litellm
  [✓] agent-api

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Bootstrap complete — 2brain AI Agent Platform
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Environment file : /path/to/.env
  Agent API        : http://localhost:8000
  Health endpoint  : http://localhost:8000/health
  LiteLLM proxy    : http://localhost:4000
  Langfuse UI      : http://localhost:3000

  API Key (X-API-Key header):
    sk-2brain-<generated>

  Quick verify:
    curl -s http://localhost:8000/health | python -m json.tool

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 3 — Verify the health endpoint

```bash
curl -s http://localhost:8000/health | python -m json.tool
```

Expected response (`200 OK`) when all dependencies are healthy:
```json
{
  "status": "ok",
  "dependencies": {
    "postgres": {"status": "healthy", "latency_ms": 3},
    "redis":    {"status": "healthy", "latency_ms": 1},
    "qdrant":   {"status": "healthy", "latency_ms": 5}
  }
}
```

If any dependency returns `"status": "unhealthy"`, the overall HTTP status is `503` and an `"error"` field explains the cause. Check `docker compose logs <service>` for details.

### Step 4 — Verify a test agent invocation

```bash
# Use the AGENT_API_KEY printed by bootstrap
export AGENT_API_KEY="sk-2brain-<your-key>"

curl -s -X POST http://localhost:8000/api/v1/run \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "00000000-0000-0000-0000-000000000001", "input": "Hello, what can you do?"}' \
  | jq .
```

Expected response (`200 OK`):
```json
{
  "job_id": "...",
  "output": "I am a 2brain AI agent. I can help you with...",
  "trace_id": "lf-...",
  "session_id": null
}
```

Open the Langfuse UI at `http://localhost:3000`, find the trace by its `trace_id`, and confirm the full execution tree is visible.

---

## Part 2 — Setting Up a New Tenant

### Step 1 — Create a tenant record (platform admin)

```bash
# Inside the agent-api container (or via psql directly)
docker compose exec agent-api python -m api.cli create-client \
  --name "Acme Corp" \
  --approval-endpoint "https://acme.example.com/hooks/approvals"
```

The command name is still `create-client` for backward compatibility; it provisions a tenant record.

Output:
```
tenant_id:   a1b2c3d4-...
api_key:     sk-acme-<generated>   ← give this to Acme's team
```

### Step 2 — (Optional) Configure a tenant policy

Create the policy directory and a Colang config file:

```bash
mkdir -p agent/guardrails/a1b2c3d4
cat > agent/guardrails/a1b2c3d4/config.co << 'EOF'
define flow block sensitive output
  user ask sensitive
  bot block sensitive

define flow mask email
  user message contains email address
  execute mask_email_action
EOF
```

The policy loader polls every 20 seconds — no restart needed. Confirm it loaded:
```bash
curl -s http://localhost:8000/health | jq .
# guardrails hot-reload logs appear in: docker compose logs agent-api
```

---

## Part 3 — Tenant Integrator: First API Call

### Authentication

All requests (except `GET /health`) require:
```
X-API-Key: sk-acme-<your-key>
```

### Synchronous invocation — single turn

```bash
curl -s -X POST https://your-platform-host/api/v1/run \
  -H "X-API-Key: $MY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "<uuid-of-agent>",
    "input": "Summarise the attached document."
  }' | jq .
```

  ### US2 practical example — support triage use case (real runnable code)

  Use case:
  - A tenant system sends a ticket text to the platform.
  - The synchronous `/run` endpoint returns a triage draft and a `trace_id`.
  - The tenant integrator stores `trace_id` for observability/audit.

  Runnable Python example:

  ```python
  #!/usr/bin/env python3
  import json
  import os
  import sys
  import urllib.request


  BASE_URL = os.getenv("AGENT_BASE_URL", "http://localhost:8000")
  API_KEY = os.getenv("AGENT_API_KEY", "")
  AGENT_ID = os.getenv("AGENT_ID", "00000000-0000-0000-0000-000000000001")

  if not API_KEY:
    print("Set AGENT_API_KEY before running this script.", file=sys.stderr)
    sys.exit(1)

  payload = {
    "agent_id": AGENT_ID,
    "input": (
      "Customer ticket: user cannot reset password and receives code 429. "
      "Provide a triage summary with priority and next action."
    ),
    "metadata": {
      "source": "support-system",
      "ticket_id": "SUP-1042",
      "tenant": "acme",
    },
  }

  req = urllib.request.Request(
    url=f"{BASE_URL}/api/v1/run",
    method="POST",
    data=json.dumps(payload).encode("utf-8"),
    headers={
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
    },
  )

  with urllib.request.urlopen(req, timeout=60) as response:
    body = json.loads(response.read().decode("utf-8"))

  print("status:", response.status)
  print("job_id:", body.get("job_id"))
  print("trace_id:", body.get("trace_id"))
  print("output:\n", body.get("output", ""))
  ```

  Run it:

  ```bash
  export AGENT_API_KEY="sk-2brain-<your-key>"
  export AGENT_ID="00000000-0000-0000-0000-000000000001"
  python examples/us2_sync_example.py
  ```

### Conversational session — multi-turn

```bash
SESSION="acme-session-001"

# Turn 1
curl -s -X POST .../api/v1/run \
  -H "X-API-Key: $MY_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"<uuid>\", \"input\": \"My name is Alice.\", \"session_id\": \"$SESSION\"}"

# Turn 2 — agent remembers Alice
curl -s -X POST .../api/v1/run \
  -H "X-API-Key: $MY_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"<uuid>\", \"input\": \"What is my name?\", \"session_id\": \"$SESSION\"}"
```

### Async batch job

```bash
# 1. Submit
JOB=$(curl -s -X POST .../api/v1/jobs \
  -H "X-API-Key: $MY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "<uuid>", "input": "Analyse the Q1 report..."}')

JOB_ID=$(echo $JOB | jq -r .job_id)

# 2. Poll until done
while true; do
  STATUS=$(curl -s .../api/v1/jobs/$JOB_ID -H "X-API-Key: $MY_API_KEY")
  STATE=$(echo $STATUS | jq -r .status)
  echo "Status: $STATE"
  [[ "$STATE" == "completed" || "$STATE" == "failed" ]] && break
  sleep 5
done

echo $STATUS | jq .output
```

### Handling a HITL approval interrupt

```bash
# Job paused for approval
STATUS=$(curl -s .../api/v1/jobs/$JOB_ID -H "X-API-Key: $MY_API_KEY")
APPROVAL_ID=$(echo $STATUS | jq -r .pending_approval_id)

# View what the agent wants to do
curl -s .../api/v1/approvals/$APPROVAL_ID -H "X-API-Key: $MY_API_KEY" | jq .

# Approve
curl -s -X POST .../api/v1/approvals/$APPROVAL_ID/decide \
  -H "X-API-Key: $MY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "reviewer_id": "alice@acme.com"}'
```

---

## Part 4 — Development Environment

### Running locally (laptop)

The compose file is fully valid for local dev. The only difference from production:
- Caddy TLS is disabled (plain HTTP on port 8000).

---

## Part 5 — Tenant CLI Quickstart

The CLI mirrors the public API rather than bypassing it. That means every command still needs the tenant’s `X-API-Key` and the same `agent_id` values used by HTTP clients.

### Step 1 — Configure a local profile

```bash
export BRAIN_API_BASE_URL="http://localhost:8000/api/v1"
export BRAIN_API_KEY="sk-2brain-<your-key>"

# planned UX
2brain config set --profile local-dev \
  --base-url "$BRAIN_API_BASE_URL" \
  --api-key "$BRAIN_API_KEY"
```

### Step 2 — Run a one-shot synchronous invocation

```bash
2brain run \
  --profile local-dev \
  --agent-id 00000000-0000-0000-0000-000000000001 \
  --input "Summarise this support request" \
  --json
```

Expected output shape:

```json
{
  "job_id": "...",
  "output": "...",
  "trace_id": "lf-...",
  "session_id": null
}
```

### Step 3 — Start or continue a session conversation

```bash
2brain session chat \
  --profile local-dev \
  --agent-id 00000000-0000-0000-0000-000000000001 \
  --session-id demo-session
```

This command opens the interactive path; when the terminal supports it, the Ink UI can render the conversation history, pending job state, and trace IDs in-place.

### Step 4 — Submit and poll an async job

```bash
2brain jobs submit \
  --profile local-dev \
  --agent-id 00000000-0000-0000-0000-000000000001 \
  --input "Generate the weekly report"

2brain jobs status --profile local-dev --job-id <job-id>
2brain jobs wait   --profile local-dev --job-id <job-id>
```

### Step 5 — Review or decide a pending approval

```bash
2brain approvals get --profile local-dev --approval-id <approval-id>
2brain approvals approve --profile local-dev --approval-id <approval-id> --reviewer-id alice@acme.com
# or
2brain approvals reject --profile local-dev --approval-id <approval-id> --reviewer-id alice@acme.com --reason "Missing legal sign-off"
```
- Log verbosity set to `DEBUG` via `LOG_LEVEL=debug` in `.env`.

```bash
# First time
bash infra/bootstrap.sh

# Subsequent starts
docker compose up -d

# Tail logs for a specific service
docker compose logs -f agent-api
docker compose logs -f agent-worker

# Run unit tests (no running stack needed)
docker compose run --rm agent-api pytest tests/ -v

# Run integration tests (requires running stack)
TEST_INTEGRATION=true docker compose run --rm agent-api pytest tests/integration/ -v
```

### Upgrading a service

Change the image tag in `infra/docker-compose.yml`, then:
```bash
docker compose pull <service>
docker compose up -d <service>
```

No data migration scripts are required for minor version upgrades. Major version upgrades will document any manual steps in the release notes.

---

## Part 5 — Observability Quick Reference

| Task | How |
|------|-----|
| View all traces | Langfuse UI → `http://localhost:3000` → Traces |
| Find trace by ID | Langfuse UI → search bar → paste `trace_id` |
| Replay a trace | Langfuse UI → trace detail → Replay button |
| View structured logs | `docker compose logs -f agent-api \| jq .` |
| Check dependency health | `curl http://localhost:8000/health` |

---

## Validation Checklist (run after bootstrap)

- [ ] `GET /health` returns `200` with all dependencies `ok`
- [ ] Synchronous invocation returns `output` + `trace_id`
- [ ] `trace_id` is findable in Langfuse UI with full execution tree
- [ ] Session turn 2 references context from turn 1
- [ ] Async job reaches `completed` status via polling
- [ ] Unauthenticated request to `/api/v1/run` returns `401`
- [ ] Second bootstrap run on existing instance does not lose data
