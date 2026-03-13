# Quickstart: 2brain AI Agent Platform

**Date**: 2026-03-14 | **Plan**: [plan.md](plan.md)

End-to-end walk-through for two audiences:
- **Agency engineers** — bootstrapping a new instance and verifying it works.
- **Client system integrators** — invoking an agent for the first time.

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
- Generates all internal secrets (Postgres password, Redis password, LiteLLM master key, Langfuse keys, internal agent API key) using `openssl rand`.
- Writes a `.env` file at the repo root (never committed).
- Prompts for the only values requiring manual input: `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY`.
- Runs `docker compose --env-file .env up -d` to start all services.
- Waits for all health checks to pass (up to 3 minutes).
- Prints a summary including the generated `AGENT_API_KEY` — **save this, it is shown only once**.

Expected output on success:
```
✓ Postgres        healthy
✓ Redis           healthy
✓ Qdrant          healthy
✓ LiteLLM         healthy
✓ Langfuse        healthy
✓ agent-api       healthy

Bootstrap complete.
AGENT_API_KEY: sk-2brain-<generated>
Langfuse UI:   http://localhost:3000  (admin / <generated-password>)
Agent API:     http://localhost:8000
```

### Step 3 — Verify the health endpoint

```bash
curl http://localhost:8000/health
```

Expected response (`200 OK`):
```json
{
  "status": "healthy",
  "dependencies": {
    "postgres": "ok",
    "redis": "ok",
    "qdrant": "ok"
  }
}
```

If any dependency shows `"error"`, check `docker compose logs <service>` for the relevant container.

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

## Part 2 — Setting Up a New Client

### Step 1 — Create a client record (platform admin)

```bash
# Inside the agent-api container (or via psql directly)
docker compose exec agent-api python -m api.cli create-client \
  --name "Acme Corp" \
  --approval-endpoint "https://acme.example.com/hooks/approvals"
```

Output:
```
client_id:   a1b2c3d4-...
api_key:     sk-acme-<generated>   ← give this to Acme's team
```

### Step 2 — (Optional) Configure a client policy

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

## Part 3 — Client System Integrator: First API Call

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
