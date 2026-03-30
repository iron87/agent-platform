# Examples

This folder contains runnable examples for implemented user stories.

## US2 - Synchronous Agent Invocation

Files:
- `examples/us2_sync_example.py`: sends a real `POST /api/v1/run` request with auth.
- `examples/us2_seed_dev.sh`: applies schema + seeds one client and one agent definition for local testing.
- `examples/us3_session_example.py`: sends three turns with the same `session_id` to validate session continuity.

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

## US3 - Conversational Session (3 turns)

Run the session example:

```bash
export AGENT_API_KEY="$(grep '^AGENT_API_KEY=' .env | cut -d'=' -f2-)"
export AGENT_ID="00000000-0000-0000-0000-000000000001"
export AGENT_SESSION_ID="us3-demo-session-1"
export AGENT_TIMEOUT_SECONDS=240
python examples/us3_session_example.py
```

Expected behavior:
- all three calls return `status=200`
- all three responses show the same `session_id`
- turn 3 can reference context from turns 1 and 2

## US4 - Web Search Tool

Files:
- `examples/us4_web_search_example.py`: runs web search in two modes — tool-only (default) or full LLM loop (`WITH_LLM=1`).

The tool uses the DuckDuckGo Instant Answer API (no API key required). It returns Wikipedia-style abstracts and related topics. Non-encyclopedic queries (e.g. "LangGraph", "FastAPI tutorial") return zero results — use broad, encyclopedic terms (e.g. "Python programming language", "machine learning").

### Mode 1 — Tool only (no LLM required)

```bash
export WEB_SEARCH_QUERY="Python programming language"
export WEB_SEARCH_MAX_RESULTS=5          # optional, default 5
export WEB_SEARCH_TIMEOUT_SECONDS=10     # optional, default 10
python examples/us4_web_search_example.py
```

Expected output:
- `Found N results` with title, URL, and snippet for each result.
- Execution time shown at the end.

### Mode 2 — Full LLM loop

Requires LiteLLM running and a registered API key (see [LiteLLM token setup](#litellm-token-setup) below).

```bash
export LITELLM_BASE_URL="http://localhost:4000"
export LITELLM_API_KEY="$(grep '^LITELLM_API_KEY=' .env | cut -d'=' -f2-)"
export WEB_SEARCH_QUERY="Python programming language"
WITH_LLM=1 python examples/us4_web_search_example.py
```

Expected output:
- LLM selects `web_search` tool and emits a `tool_calls` finish reason.
- Tool executes and returns raw results.
- LLM synthesises a natural-language answer from the results.

### LiteLLM token setup

Bootstrap generates the `LITELLM_API_KEY` secret but does **not** register it as a virtual key in LiteLLM's database. If you see `HTTP 401 / token_not_found_in_db`, register it once:

```bash
MASTER=$(grep '^LITELLM_MASTER_KEY=' .env | cut -d'=' -f2-)
API_KEY=$(grep '^LITELLM_API_KEY=' .env | cut -d'=' -f2-)

curl -s -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d "{\"key\": \"$API_KEY\", \"key_alias\": \"agent-platform-internal\"}"
```

The command registers `LITELLM_API_KEY` in `LiteLLM_VerificationTokenTable`. You only need to do this once per stack instance (or after a DB wipe).

**Quick local-dev shortcut**: set `LITELLM_API_KEY` to the same value as `LITELLM_MASTER_KEY` in `.env` and restart the stack — the master key bypasses the DB lookup entirely:

```bash
MASTER=$(grep '^LITELLM_MASTER_KEY=' .env | cut -d'=' -f2-)
sed -i '' "s/^LITELLM_API_KEY=.*/LITELLM_API_KEY=$MASTER/" .env
docker compose -f infra/docker-compose.light.yml --env-file .env up -d --force-recreate litellm
```

### Troubleshooting

If you get `No web results found`:
- the query is not encyclopedic enough for the DuckDuckGo Instant Answer API.
- try broader terms: "Python", "machine learning", "artificial intelligence".

If Mode 2 fails with `HTTP 401`:
- register the virtual key as shown above.

If Mode 2 fails with `ConnectionRefusedError`:
- make sure the stack is running: `bash infra/bootstrap-light.sh`
