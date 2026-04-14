#!/usr/bin/env bash
set -euo pipefail

# US11 example: RAG flow via 2brain CLI + bash (no Python).
# Steps:
# 1) Configure CLI profile
# 2) Create agent with semantic memory enabled
# 3) Seed facts
# 4) Query in a different session to verify retrieval

BASE_URL="${BASE_URL:-http://localhost:8000/api/v1}"
API_KEY="${AGENT_API_KEY:-}"
PROFILE="${PROFILE:-rag-demo}"
MODEL_ALIAS="${MODEL_ALIAS:-fast}"
TENANT_ID="${AGENT_TENANT_ID:-11111111-1111-1111-1111-111111111111}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"

if [[ -z "${API_KEY}" ]]; then
  echo "AGENT_API_KEY is required" >&2
  exit 1
fi

if ! command -v 2brain >/dev/null 2>&1; then
  echo "2brain command not found. Install/build tenant CLI first." >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT_FILE_REL="examples/prompts/us11_rag_cli_prompt.txt"
PROMPT_FILE_ABS="${REPO_ROOT}/${PROMPT_FILE_REL}"
mkdir -p "$(dirname "${PROMPT_FILE_ABS}")"
cat > "${PROMPT_FILE_ABS}" <<'PROMPT'
You are a retrieval-first assistant.
When the user asks factual questions, prioritize tenant semantic memory,
then answer concisely and explicitly cite recovered facts in plain language.
PROMPT

TS="$(date +%s)"
AGENT_NAME="rag-cli-${TS}"
SEED_SESSION_ID="rag-seed-${TS}"
QUERY_SESSION_ID="rag-query-${TS}"

printf "\n[1/5] Configure CLI profile '%s'...\n" "${PROFILE}"
2brain config set --profile "${PROFILE}" --base-url "${BASE_URL}" --api-key "${API_KEY}" >/dev/null

printf "[2/5] Create semantic-memory agent '%s'...\n" "${AGENT_NAME}"
CREATE_JSON="$(2brain agents create \
  --profile "${PROFILE}" \
  --name "${AGENT_NAME}" \
  --prompt-file "${PROMPT_FILE_REL}" \
  --model-alias "${MODEL_ALIAS}" \
  --semantic-memory-enabled \
  --json)"

AGENT_ID="$(printf '%s' "${CREATE_JSON}" | grep -Eo '"id"[[:space:]]*:[[:space:]]*"[^"]+"' | head -n1 | sed -E 's/.*"([^"]+)"/\1/')"
if [[ -z "${AGENT_ID}" ]]; then
  echo "Failed to parse agent id from CLI output:" >&2
  echo "${CREATE_JSON}" >&2
  exit 1
fi

printf "[3/5] Seed memory fact #1...\n"
2brain run \
  --profile "${PROFILE}" \
  --agent-id "${AGENT_ID}" \
  --session-id "${SEED_SESSION_ID}" \
  --input "Fact: Customer ACME runs PostgreSQL 16 in production." \
  --json >/dev/null

printf "[4/5] Seed memory fact #2...\n"
2brain run \
  --profile "${PROFILE}" \
  --agent-id "${AGENT_ID}" \
  --session-id "${SEED_SESSION_ID}" \
  --input "Fact: ACME technical owner is Luca Bianchi." \
  --json >/dev/null

printf "[5/5] Query from a different session (RAG check)...\n\n"
2brain run \
  --profile "${PROFILE}" \
  --agent-id "${AGENT_ID}" \
  --session-id "${QUERY_SESSION_ID}" \
  --input "Who is ACME's technical owner and which database do they use in production?" \
  --json

echo
echo "Qdrant verification (collection: ${TENANT_ID}_memory):"
if command -v curl >/dev/null 2>&1; then
  COLLECTION_NAME="${TENANT_ID}_memory"
  if curl -fsS "${QDRANT_URL}/collections/${COLLECTION_NAME}" >/dev/null; then
    echo "- collection exists"
    COUNT_RESPONSE="$(curl -fsS -X POST "${QDRANT_URL}/collections/${COLLECTION_NAME}/points/count" \
      -H "Content-Type: application/json" \
      -d '{"exact":true}' || true)"
    POINT_COUNT="$(printf '%s' "${COUNT_RESPONSE}" | grep -Eo '"count"[[:space:]]*:[[:space:]]*[0-9]+' | head -n1 | sed -E 's/.*: *([0-9]+)/\1/')"
    if [[ -n "${POINT_COUNT}" ]]; then
      echo "- points in collection: ${POINT_COUNT}"
    else
      echo "- points count unavailable (raw response below)"
      echo "${COUNT_RESPONSE}"
    fi
  else
    echo "- collection not found yet (check tenant id / qdrant URL / async indexing delay)"
  fi
else
  echo "- curl not available: skipped"
fi

echo
echo "Done."
echo "Profile:      ${PROFILE}"
echo "Agent name:   ${AGENT_NAME}"
echo "Agent id:     ${AGENT_ID}"
echo "Seed session: ${SEED_SESSION_ID}"
echo "Query session:${QUERY_SESSION_ID}"
echo "Tenant id:    ${TENANT_ID}"
echo "Qdrant URL:   ${QDRANT_URL}"
