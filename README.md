# 2brain Platform

A self-hosted AI agent platform for engineering teams that build and operate AI agents for clients.

The project is cloud-agnostic and designed to run on a single Docker host, with API access, worker orchestration, model routing via LiteLLM aliases, and observability services.

Architecture diagram: [docs/architecture.md](docs/architecture.md)

## What This Project Is

2brain provides a foundation to:

- Define and run agents in a controlled runtime.
- Expose agent capabilities through stable HTTP APIs.
- Isolate client workloads in a multi-tenant architecture.
- Trace, inspect, and debug executions.

Current repository status: foundational runtime and US1-US2 workflows are implemented.

## Use Cases

Main use cases this platform targets:

- One-command bootstrap of a complete self-hosted AI stack on a fresh machine.
- Synchronous agent invocation from client systems.
- Conversational sessions with contextual memory.
- Tool-enabled agents for multi-step automation.
- Async batch processing with polling/retrieval.
- Provider-agnostic model routing and fallback.
- Trace review and replay for production diagnostics.
- Per-client policy enforcement (redaction/blocking/injection checks).
- Human-in-the-loop approvals for high-risk actions.

## Current Implementation Status

Implemented tasks so far:

- T001: Python project metadata and dependency groups in pyproject.toml.
- T002: Developer targets in Makefile for bootstrap, run, and test.
- T003: Base package scaffolding for agent, api, and worker with __init__.py files.
- T004: Documented required environment variables in infra/.env.example.
- T005: LiteLLM alias template in infra/litellm/config.yaml.template (default, fast, embedding).
- T006: Single-host Docker Compose stack for caddy, postgres, redis, qdrant, litellm, langfuse, clickhouse, minio, agent-api, and agent-worker.
- T007: Bootstrap script for secret generation, startup, and dependency wait logic.
- T008: Caddy reverse proxy configuration with internal TLS and agent-api routing.

## How To Use

### Runnable Examples

- Examples index: [examples/README.md](examples/README.md)
- US2 sync invoke script: [examples/us2_sync_example.py](examples/us2_sync_example.py)
- US2 seed/setup helper: [examples/us2_seed_dev.sh](examples/us2_seed_dev.sh)
- US3 session invoke script: [examples/us3_session_example.py](examples/us3_session_example.py)

### Prerequisites

- Python 3.12+
- Docker + Docker Compose
- Make

### 1) Install local development dependencies

```bash
python -m pip install -e '.[dev]'
```

### 2) Prepare environment

```bash
cp infra/.env.example .env
```

Local-first strategy (recommended for development):

- Configure local endpoint and model aliases:
- `LOCAL_LLM_API_BASE`
- `LOCAL_DEFAULT_MODEL`
- `LOCAL_FAST_MODEL`
- `LOCAL_EMBEDDING_MODEL`
- `LOCAL_EMBEDDING_API_BASE`

Cloud strategy:

- Customize `infra/litellm/config.yaml.template` to cloud providers.
- Set provider keys (`ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY`).

### 3) Bootstrap stack

```bash
bash infra/bootstrap.sh
```

Lightweight mode (recommended on Mac laptops):

```bash
bash infra/bootstrap-light.sh
```

This starts only `postgres`, `redis`, `litellm`, and `agent-api`.

### 4) Useful development commands

```bash
make PYTHON=/path/to/python test-all
make PYTHON=/path/to/python test-integration
make PYTHON=/path/to/python test-full
make PYTHON=/path/to/python run-api
make PYTHON=/path/to/python run-worker
make bootstrap
make bootstrap-light
docker compose -f infra/docker-compose.yml --env-file .env config
docker compose -f infra/docker-compose.light.yml --env-file .env config
```

## How To Test

### A) Code quality and unit-level checks

```bash
make PYTHON=/path/to/python test-all
```

This runs:

- pytest (default suite)
- ruff
- mypy

### B) Integration suite (opt-in)

```bash
make PYTHON=/path/to/python test-integration
```

`test-integration` is opt-in and may be skipped when the runtime stack is not up.

### C) Full local pipeline

```bash
make PYTHON=/path/to/python test-full
```

### D) Runtime stack verification (up and running)

1. Validate compose rendering:

```bash
docker compose -f infra/docker-compose.yml --env-file .env config
```

2. Start stack:

```bash
bash infra/bootstrap.sh
```

Or start lightweight stack:

```bash
bash infra/bootstrap-light.sh
```

3. Check service status:

```bash
docker compose -f infra/docker-compose.yml --env-file .env ps
docker compose -f infra/docker-compose.light.yml --env-file .env ps
```

4. Probe core dependencies:

```bash
curl -f http://localhost:6333/healthz
curl -f http://localhost:4000/health/liveliness
curl -f http://localhost:8000/live
curl -i http://localhost:8000/health
curl -I http://localhost:3000
```

Notes:
- `/live` is liveness (process up) and is used by Docker healthcheck.
- `/health` is readiness (postgres/redis/qdrant probes) and can return 503 when dependencies are degraded.

### E) Focused artifact checks

```bash
python -c "import agent, api, worker; print('ok')"
python -c "from pathlib import Path; print((Path('infra/.env.example').exists(), Path('infra/litellm/config.yaml.template').exists()))"
python -c "from pathlib import Path; print((Path('infra/docker-compose.yml').exists(), Path('infra/bootstrap.sh').exists(), Path('infra/caddy/Caddyfile').exists()))"
```

## Notes On Current Scope

- Phase 1 is complete and validated with automated checks.
- Runtime API and business endpoints are implemented in later phases.

## Documentation Maintenance Rule

This README is a living document. After each implemented task in specs/001-ai-agent-platform/tasks.md, it must be updated with:

1. What was implemented.
2. How to use it.
3. How to verify it with tests or commands.

## Repository Structure

- agent/: agent runtime and orchestration.
- api/: FastAPI application.
- worker/: worker and async jobs.
- infra/: bootstrap and infrastructure configuration.
- tests/: unit and integration tests.
- specs/: specification, plan, and task documents.
