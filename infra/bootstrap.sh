#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
ENV_EXAMPLE="$ROOT_DIR/infra/.env.example"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.yml"
FORCE_REGENERATE="${FORCE_REGENERATE:-false}"

require_command() {
	if ! command -v "$1" >/dev/null 2>&1; then
		echo "Error: Missing required command: $1" >&2
		exit 1
	fi
}

preflight_checks() {
	require_command docker
	require_command openssl
	require_command curl

	# Verify docker daemon is running
	if ! docker info >/dev/null 2>&1; then
		echo "Error: Docker daemon is not running." >&2
		exit 1
	fi

	# Verify compose file exists
	if [[ ! -f "$COMPOSE_FILE" ]]; then
		echo "Error: Compose file not found at $COMPOSE_FILE" >&2
		exit 1
	fi

	# Verify .env.example exists
	if [[ ! -f "$ENV_EXAMPLE" ]]; then
		echo "Error: $ENV_EXAMPLE not found. Cannot seed environment." >&2
		exit 1
	fi
}

set_env_value() {
	local key="$1"
	local value="$2"

	if grep -q "^${key}=" "$ENV_FILE"; then
		python - <<'PY' "$ENV_FILE" "$key" "$value"
from pathlib import Path
import sys

env_file = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
lines = env_file.read_text(encoding="utf-8").splitlines()
updated = []
for line in lines:
		if line.startswith(f"{key}="):
				updated.append(f"{key}={value}")
		else:
				updated.append(line)
env_file.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
	else
		printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
	fi
}

get_env_value() {
	local key="$1"
	grep -E "^${key}=" "$ENV_FILE" | head -n1 | cut -d'=' -f2-
}

ensure_default_value() {
	local key="$1"
	local default_value="$2"
	local current
	current="$(grep -E "^${key}=" "$ENV_FILE" | cut -d'=' -f2- || true)"

	if [[ -z "$current" ]]; then
		set_env_value "$key" "$default_value"
	fi
}

ensure_env_file() {
	if [[ ! -f "$ENV_FILE" ]]; then
		echo "No .env found — creating from $ENV_EXAMPLE"
		cp "$ENV_EXAMPLE" "$ENV_FILE"
	else
		echo ".env already exists — skipping creation (use FORCE_REGENERATE=true to reset secrets)"
	fi
}

ensure_secret() {
	local key="$1"
	local prefix="${2:-}"
	local current
	current="$(grep -E "^${key}=" "$ENV_FILE" | cut -d'=' -f2- || true)"

	local is_placeholder=false
	case "$current" in
		""|"change-me"|"sk-2brain-change-me"|"sk-litellm-master-change-me"|\
		"sk-agent-platform-internal"|"pk-change-me"|"sk-change-me")
			is_placeholder=true
			;;
	esac

	if [[ "$is_placeholder" == "true" || "$FORCE_REGENERATE" == "true" ]]; then
		set_env_value "$key" "${prefix}$(openssl rand -hex 16)"
	fi
}

wait_for_http() {
	local url="$1"
	local label="$2"
	local attempts="${3:-60}"

	for ((i=1; i<=attempts; i++)); do
		if curl -fsS "$url" >/dev/null 2>&1; then
			echo "  [✓] $label"
			return 0
		fi
		sleep 2
	done

	echo "  [✗] Timed out waiting for $label at $url" >&2
	return 1
}

print_summary() {
	local api_key
	api_key="$(grep -E "^AGENT_API_KEY=" "$ENV_FILE" | cut -d'=' -f2- || true)"

	echo ""
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	echo " Bootstrap complete — 2brain AI Agent Platform"
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	echo ""
	echo "  Environment file : $ENV_FILE"
	echo "  Agent API        : http://localhost:8000"
	echo "  Health endpoint  : http://localhost:8000/health"
	echo "  LiteLLM proxy    : http://localhost:4000"
	echo "  Langfuse UI      : http://localhost:3000"
	echo ""
	echo "  API Key (X-API-Key header):"
	echo "    $api_key"
	echo ""
	echo "  Quick verify:"
	echo "    curl -s http://localhost:8000/health | python -m json.tool"
	echo ""
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

main() {
	echo "==> Running preflight checks..."
	preflight_checks

	echo "==> Preparing environment..."
	ensure_env_file
	ensure_secret AGENT_API_KEY "sk-2brain-"
	ensure_secret LITELLM_API_KEY "sk-agent-"
	ensure_secret POSTGRES_PASSWORD
	ensure_secret REDIS_PASSWORD
	ensure_secret LITELLM_MASTER_KEY "sk-litellm-"
	ensure_secret LANGFUSE_PUBLIC_KEY "pk-lf-"
	ensure_secret LANGFUSE_SECRET_KEY "sk-lf-"
	ensure_secret MINIO_ROOT_PASSWORD
	ensure_secret CLICKHOUSE_PASSWORD
	ensure_default_value LITELLM_TENANT_BUDGET_TOTAL "1000.0"
	ensure_default_value LITELLM_TENANT_BUDGET_DURATION "30d"

	# Keep derived connection URLs consistent with generated secrets.
	local postgres_host postgres_port postgres_db postgres_user postgres_password
	local redis_host redis_port redis_password
	postgres_host="$(get_env_value POSTGRES_HOST)"
	postgres_port="$(get_env_value POSTGRES_PORT)"
	postgres_db="$(get_env_value POSTGRES_DB)"
	postgres_user="$(get_env_value POSTGRES_USER)"
	postgres_password="$(get_env_value POSTGRES_PASSWORD)"
	redis_host="$(get_env_value REDIS_HOST)"
	redis_port="$(get_env_value REDIS_PORT)"
	redis_password="$(get_env_value REDIS_PASSWORD)"

	set_env_value "DATABASE_URL" "postgresql+asyncpg://${postgres_user}:${postgres_password}@${postgres_host}:${postgres_port}/${postgres_db}"
	set_env_value "REDIS_URL" "redis://:${redis_password}@${redis_host}:${redis_port}/0"

	echo "==> Starting services..."
	# Ensure compose interpolation uses the just-prepared .env values even if
	# parent shell exported stale placeholders.
	set -a
	# shellcheck disable=SC1090
	source "$ENV_FILE"
	set +a
	docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

	echo "==> Waiting for dependencies to become healthy..."
	wait_for_http "http://localhost:6333/healthz" "qdrant"
	wait_for_http "http://localhost:3000" "langfuse"
	wait_for_http "http://localhost:4000/health/liveliness" "litellm"
	wait_for_http "http://localhost:8000/" "agent-api"

	print_summary
}

main "$@"

