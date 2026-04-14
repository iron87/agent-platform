#!/usr/bin/env bash
set -euo pipefail

# US12 example: RAG with file ingestion via 2brain CLI + bash.
# Reads all .txt files in examples/data/mtb and ingests content as memory facts,
# then runs a retrieval query from a different session.

BASE_URL="${BASE_URL:-http://localhost:8000/api/v1}"
API_KEY="${AGENT_API_KEY:-}"
PROFILE="${PROFILE:-rag-files-demo}"
MODEL_ALIAS="${MODEL_ALIAS:-fast}"
TENANT_ID="${AGENT_TENANT_ID:-11111111-1111-1111-1111-111111111111}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
DATA_DIR="${DATA_DIR:-examples/data/mtb}"
CLI_RUN_TIMEOUT_SECONDS="${CLI_RUN_TIMEOUT_SECONDS:-300}"

if [[ -z "${API_KEY}" ]]; then
  echo "AGENT_API_KEY is required" >&2
  exit 1
fi

if ! command -v 2brain >/dev/null 2>&1; then
  echo "2brain command not found. Install/build tenant CLI first." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required" >&2
  exit 1
fi

run_with_retry() {
  local max_attempts=3
  local attempt=1

  while true; do
    if "$@"; then
      return 0
    fi

    if [[ "${attempt}" -ge "${max_attempts}" ]]; then
      return 1
    fi

    echo "Transient failure, retrying (${attempt}/${max_attempts})..." >&2
    attempt=$((attempt + 1))
    sleep 2
  done
}

run_with_optional_timeout() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "${CLI_RUN_TIMEOUT_SECONDS}" "$@"
    return $?
  fi

  if command -v gtimeout >/dev/null 2>&1; then
    gtimeout "${CLI_RUN_TIMEOUT_SECONDS}" "$@"
    return $?
  fi

  "$@"
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT_FILE_REL="examples/prompts/us12_rag_file_prompt.txt"
PROMPT_FILE_ABS="${REPO_ROOT}/${PROMPT_FILE_REL}"
mkdir -p "$(dirname "${PROMPT_FILE_ABS}")"
cat > "${PROMPT_FILE_ABS}" <<'PROMPT'
You are a retrieval-first MTB assistant.
Use semantic memory facts from ingested files before answering.
When possible, cite which source file the information likely came from.
PROMPT

if [[ ! -d "${REPO_ROOT}/${DATA_DIR}" ]]; then
  echo "Data directory not found: ${REPO_ROOT}/${DATA_DIR}" >&2
  exit 1
fi

if ! curl -fsS "${QDRANT_URL}/healthz" >/dev/null; then
  if [[ "${QDRANT_URL}" == *"qdrant:"* ]]; then
    echo "Qdrant at ${QDRANT_URL} not reachable from host, retrying with http://localhost:6333" >&2
    QDRANT_URL="http://localhost:6333"
  fi
fi

if ! curl -fsS "${QDRANT_URL}/healthz" >/dev/null; then
  echo "Qdrant is not reachable at ${QDRANT_URL}" >&2
  echo "Start it with: docker compose -f infra/docker-compose.yml --env-file .env up -d qdrant" >&2
  exit 1
fi

TS="$(date +%s)"
AGENT_NAME="rag-files-${TS}"
INGEST_SESSION_ID="rag-files-seed-${TS}"
QUERY_SESSION_ID="rag-files-query-${TS}"

printf "\n[1/6] Configure CLI profile '%s'...\n" "${PROFILE}"
2brain config set --profile "${PROFILE}" --base-url "${BASE_URL}" --api-key "${API_KEY}" >/dev/null

printf "[2/6] Create semantic-memory agent '%s'...\n" "${AGENT_NAME}"
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

printf "[3/6] Ingest .txt files from %s...\n" "${DATA_DIR}"
echo "This step can take a few minutes depending on local model speed."
INGESTED=0
while IFS= read -r -d '' file; do
  rel="${file#${REPO_ROOT}/}"
  content="$(cat "${file}")"

  # Prefix with source marker so retrieval answers can reference origin.
  payload="Source file: ${rel}\n\n${content}"

  echo "- ingesting ${rel}"
  ingest_output="$(mktemp)"
  if ! run_with_retry run_with_optional_timeout 2brain run \
    --profile "${PROFILE}" \
    --agent-id "${AGENT_ID}" \
    --session-id "${INGEST_SESSION_ID}" \
    --input "${payload}" \
    --json >"${ingest_output}" 2>&1; then
    echo "Ingestion failed for ${rel}. Last CLI output:" >&2
    tail -n 60 "${ingest_output}" >&2 || true
    rm -f "${ingest_output}"
    exit 1
  fi
  rm -f "${ingest_output}"

  INGESTED=$((INGESTED + 1))
  echo "- ingested ${rel}"
done < <(find "${REPO_ROOT}/${DATA_DIR}" -type f -name '*.txt' -print0 | sort -z)

if [[ "${INGESTED}" -eq 0 ]]; then
  echo "No .txt files found in ${DATA_DIR}" >&2
  exit 1
fi

printf "[4/6] Run retrieval query from a different session...\n\n"
query_output="$(mktemp)"
if ! run_with_retry run_with_optional_timeout 2brain run \
  --profile "${PROFILE}" \
  --agent-id "${AGENT_ID}" \
  --session-id "${QUERY_SESSION_ID}" \
  --input "Based on MTB documents, explain trail bike setup priorities, suspension baseline sag, and one nutrition guideline for rides over 90 minutes." \
  --json >"${query_output}" 2>&1; then
  echo "Retrieval query failed. Last CLI output:" >&2
  tail -n 60 "${query_output}" >&2 || true
  rm -f "${query_output}"
  exit 1
fi
cat "${query_output}"
rm -f "${query_output}"

printf "\n[5/6] Verify Qdrant collection and point count...\n"
COLLECTION_NAME="${TENANT_ID}_memory"
if curl -fsS "${QDRANT_URL}/collections/${COLLECTION_NAME}" >/dev/null; then
  echo "- collection exists: ${COLLECTION_NAME}"
  COUNT_RESPONSE="$(curl -fsS -X POST "${QDRANT_URL}/collections/${COLLECTION_NAME}/points/count" \
    -H "Content-Type: application/json" \
    -d '{"exact":true}')"
  POINT_COUNT="$(printf '%s' "${COUNT_RESPONSE}" | grep -Eo '"count"[[:space:]]*:[[:space:]]*[0-9]+' | head -n1 | sed -E 's/.*: *([0-9]+)/\1/')"
  echo "- points in collection: ${POINT_COUNT:-unknown}"
else
  echo "- collection not found: ${COLLECTION_NAME}" >&2
  exit 1
fi

printf "[6/6] Summary\n"
echo "Done."
echo "Profile:        ${PROFILE}"
echo "Agent name:     ${AGENT_NAME}"
echo "Agent id:       ${AGENT_ID}"
echo "Ingested files: ${INGESTED}"
echo "Ingest session: ${INGEST_SESSION_ID}"
echo "Query session:  ${QUERY_SESSION_ID}"
echo "Qdrant URL:     ${QDRANT_URL}"
