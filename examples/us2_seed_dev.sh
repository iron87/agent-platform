#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.yml"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing .env at $ENV_FILE. Run: bash infra/bootstrap.sh" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "${AGENT_API_KEY:-}" ]]; then
  echo "AGENT_API_KEY missing in .env" >&2
  exit 1
fi

echo "Applying base schema..."
for migration in "$ROOT_DIR"/infra/migrations/*.sql; do
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres \
    sh -lc 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    < "$migration" >/dev/null
done

echo "Seeding dev tenant + agent definition for US2..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres \
  sh -lc 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<SQL
INSERT INTO tenants (id, name, api_key_hash, approval_endpoint, is_active)
VALUES (
  '11111111-1111-1111-1111-111111111111',
  'Acme Dev',
  '${AGENT_API_KEY}',
  NULL,
  true
)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  api_key_hash = EXCLUDED.api_key_hash,
  is_active = EXCLUDED.is_active;

INSERT INTO agent_definitions (
  id, name, model_alias, prompt_file, graph_type, tools, hitl_tools,
  max_execution_seconds, semantic_memory_enabled, version
)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'support-triage',
  'default',
  'examples/prompts/us2_support_prompt.txt',
  'conversational',
  ARRAY[]::text[],
  ARRAY[]::text[],
  60,
  false,
  1
)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  model_alias = EXCLUDED.model_alias,
  prompt_file = EXCLUDED.prompt_file,
  graph_type = EXCLUDED.graph_type,
  max_execution_seconds = EXCLUDED.max_execution_seconds,
  semantic_memory_enabled = EXCLUDED.semantic_memory_enabled,
  version = EXCLUDED.version;
SQL

echo "US2 dev seed completed."
echo "Tenant ID: 11111111-1111-1111-1111-111111111111"
echo "Agent ID:  00000000-0000-0000-0000-000000000001"
echo "Use this API key for examples: $AGENT_API_KEY"
echo "Export for examples:"
echo "  export AGENT_ID=00000000-0000-0000-0000-000000000001"
echo "  export AGENT_API_KEY=$AGENT_API_KEY"
