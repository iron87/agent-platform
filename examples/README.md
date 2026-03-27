# Examples

This folder contains runnable examples for implemented user stories.

## US2 - Synchronous Agent Invocation

Files:
- `examples/us2_sync_example.py`: sends a real `POST /api/v1/run` request with auth.
- `examples/us2_seed_dev.sh`: applies schema + seeds one client and one agent definition for local testing.

### End-to-end run (local)

1. Bootstrap stack:

```bash
bash infra/bootstrap.sh
```

Or lightweight mode (Mac-friendly):

```bash
bash infra/bootstrap-light.sh
```

2. Seed required data for US2:

```bash
bash examples/us2_seed_dev.sh
```

If you already seeded before, run it again after updates (it performs an upsert).

3. Run the example:

```bash
export AGENT_API_KEY="$(grep '^AGENT_API_KEY=' .env | cut -d'=' -f2-)"
export AGENT_ID="00000000-0000-0000-0000-000000000001"
export AGENT_TIMEOUT_SECONDS=180
python examples/us2_sync_example.py
```

Expected output:
- `status: 200`
- a non-empty `output`
- a `trace_id` value (can be null if observability disabled/unavailable)

### Troubleshooting

If you get `HTTP 401`:
- verify `AGENT_API_KEY` is the one from `.env`.
- rerun `bash examples/us2_seed_dev.sh`.

If you get `HTTP 500`:
- check service logs:

```bash
docker compose -f infra/docker-compose.yml --env-file .env logs --tail=120 agent-api
docker compose -f infra/docker-compose.light.yml --env-file .env logs --tail=120 agent-api
```

If the example fails with `TimeoutError: timed out`:
- increase `AGENT_TIMEOUT_SECONDS` (first local model run can take >60s).
- pre-warm Ollama model once, then retry the example.
- restart `litellm` after config changes:

```bash
docker compose -f infra/docker-compose.light.yml --env-file .env up -d --force-recreate litellm
```

If bootstrap fails on dependencies:
- rerun bootstrap and wait for health checks:

```bash
bash infra/bootstrap.sh
```
