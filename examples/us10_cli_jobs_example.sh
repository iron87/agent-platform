#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000/api/v1}"
API_KEY="${AGENT_API_KEY:-}"
AGENT_ID="${AGENT_ID:-00000000-0000-0000-0000-000000000001}"

if [[ -z "${API_KEY}" ]]; then
  echo "AGENT_API_KEY is required"
  exit 1
fi

2brain config set --profile local-dev --base-url "${BASE_URL}" --api-key "${API_KEY}" >/dev/null
JOB_JSON="$(2brain jobs submit --profile local-dev --agent-id "${AGENT_ID}" --input "Generate a queue health report" --json)"
JOB_ID="$(echo "${JOB_JSON}" | python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')"

echo "job_id=${JOB_ID}"
2brain jobs status --profile local-dev --job-id "${JOB_ID}" --json
2brain jobs wait --profile local-dev --job-id "${JOB_ID}" --timeout 180 --json
