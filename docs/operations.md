# Operations Runbook

## Scope

This runbook covers restart, upgrade, and troubleshooting for the local and containerized 2brain platform stack.

## Restart Procedures

### Full stack restart (light profile)

```bash
bash infra/bootstrap-light.sh
```

### Full stack restart (full profile)

```bash
bash infra/bootstrap.sh
```

### Restart a single service

```bash
docker compose -f infra/docker-compose.light.yml --env-file .env up -d --force-recreate agent-api
# or (full stack file)
docker compose -f infra/docker-compose.yml --env-file .env up -d --force-recreate agent-api
```

Common service names:
- agent-api
- agent-worker
- litellm
- postgres
- redis
- qdrant

## Upgrade Procedure

1. Pull latest code and review migrations/contracts:

```bash
git pull
```

2. Rebuild updated services:

```bash
docker compose -f infra/docker-compose.light.yml --env-file .env build agent-api agent-worker litellm
```

3. Apply schema migrations (if any new SQL files were added):

```bash
docker compose -f infra/docker-compose.light.yml --env-file .env exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /migrations/001_initial_schema.sql
```

4. Restart services:

```bash
docker compose -f infra/docker-compose.light.yml --env-file .env up -d
```

5. Verify health and key user flows:

```bash
curl -s http://localhost:8000/health | jq .
npm run cli:build
npm run cli:test
```

## Troubleshooting

### API returns 401 Invalid API key

- Ensure `X-API-Key` matches seeded tenant key.
- Re-seed local tenant if needed:

```bash
bash examples/us2_seed_dev.sh
```

### Jobs stuck in pending

- Check worker logs:

```bash
docker compose -f infra/docker-compose.light.yml --env-file .env logs --tail=200 agent-worker
```

- Recreate worker:

```bash
docker compose -f infra/docker-compose.light.yml --env-file .env up -d --force-recreate agent-worker
```

### Approval remains pending forever

- Confirm approval timeout sweeper runs in your process model.
- Check approval endpoints and job status:

```bash
2brain approvals get --profile local-dev --approval-id <approval-id>
2brain jobs status --profile local-dev --job-id <job-id>
```

### LiteLLM or model routing failures

- Validate LiteLLM config and env aliases (`default`, `fast`, `embedding`).
- Restart LiteLLM after env/template changes:

```bash
docker compose -f infra/docker-compose.light.yml --env-file .env up -d --force-recreate litellm
```

### DB connection failures

- Verify `DATABASE_URL` in `.env` and postgres container state.
- Check connectivity from API container:

```bash
docker compose -f infra/docker-compose.light.yml --env-file .env exec agent-api env | grep DATABASE_URL
```

## Useful Diagnostics

```bash
docker compose -f infra/docker-compose.light.yml --env-file .env ps
docker compose -f infra/docker-compose.light.yml --env-file .env logs --tail=120 agent-api
docker compose -f infra/docker-compose.light.yml --env-file .env logs --tail=120 agent-worker
pytest -q tests/routes tests/graphs tests/cli
```
