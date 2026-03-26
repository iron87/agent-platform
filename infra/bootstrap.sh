#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
ENV_EXAMPLE="$ROOT_DIR/infra/.env.example"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.yml"

require_command() {
	if ! command -v "$1" >/dev/null 2>&1; then
		echo "Missing required command: $1" >&2
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

ensure_env_file() {
	if [[ ! -f "$ENV_FILE" ]]; then
		cp "$ENV_EXAMPLE" "$ENV_FILE"
	fi
}

ensure_secret() {
	local key="$1"
	local prefix="${2:-}"
	local current
	current="$(grep -E "^${key}=" "$ENV_FILE" | cut -d'=' -f2- || true)"

	if [[ -z "$current" || "$current" == "change-me" || "$current" == sk-2brain-change-me || "$current" == sk-litellm-master-change-me || "$current" == sk-agent-platform-internal || "$current" == pk-change-me || "$current" == sk-change-me ]]; then
		set_env_value "$key" "${prefix}$(openssl rand -hex 16)"
	fi
}

wait_for_http() {
	local url="$1"
	local label="$2"
	local attempts="${3:-60}"

	for ((i=1; i<=attempts; i++)); do
		if curl -fsS "$url" >/dev/null 2>&1; then
			echo "healthy: $label"
			return 0
		fi
		sleep 2
	done

	echo "Timed out waiting for $label at $url" >&2
	return 1
}

main() {
	require_command docker
	require_command openssl
	require_command curl

	ensure_env_file
	ensure_secret AGENT_API_KEY "sk-2brain-"
	ensure_secret POSTGRES_PASSWORD
	ensure_secret REDIS_PASSWORD
	ensure_secret LITELLM_MASTER_KEY "sk-litellm-"
	ensure_secret LANGFUSE_PUBLIC_KEY "pk-lf-"
	ensure_secret LANGFUSE_SECRET_KEY "sk-lf-"
	ensure_secret MINIO_ROOT_PASSWORD
	ensure_secret CLICKHOUSE_PASSWORD

	docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

	wait_for_http "http://localhost:6333/healthz" "qdrant"
	wait_for_http "http://localhost:3000" "langfuse"
	wait_for_http "http://localhost:4000/health/liveliness" "litellm"
	wait_for_http "http://localhost:8000" "agent-api"

	echo
	echo "Bootstrap complete"
	echo "Environment file: $ENV_FILE"
	echo "Agent API: http://localhost:8000"
	echo "LiteLLM: http://localhost:4000"
	echo "Langfuse: http://localhost:3000"
}

main "$@"
