#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000/api/v1}"
API_KEY="${AGENT_API_KEY:-}"
APPROVAL_ID="${AGENT_APPROVAL_ID:-}"
REVIEWER_ID="${AGENT_REVIEWER_ID:-ops@example.com}"
DECISION="${AGENT_APPROVAL_DECISION:-approve}"
REASON="${AGENT_APPROVAL_REASON:-Approved via CLI example}"

if [[ -z "${API_KEY}" ]]; then
  echo "AGENT_API_KEY is required"
  exit 1
fi

if [[ -z "${APPROVAL_ID}" ]]; then
  echo "AGENT_APPROVAL_ID is required"
  exit 1
fi

2brain config set --profile local-dev --base-url "${BASE_URL}" --api-key "${API_KEY}" >/dev/null
2brain approvals get --profile local-dev --approval-id "${APPROVAL_ID}" --json

if [[ "${DECISION}" == "reject" ]]; then
  2brain approvals reject \
    --profile local-dev \
    --approval-id "${APPROVAL_ID}" \
    --reviewer-id "${REVIEWER_ID}" \
    --reason "${REASON}" \
    --json
else
  2brain approvals approve \
    --profile local-dev \
    --approval-id "${APPROVAL_ID}" \
    --reviewer-id "${REVIEWER_ID}" \
    --reason "${REASON}" \
    --json
fi
