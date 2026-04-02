# Examples

This folder contains runnable examples for implemented user stories.

## US2 - Synchronous Agent Invocation

Files:
- `examples/us2_sync_example.py`: sends a real `POST /api/v1/run` request with auth.
- `examples/us2_seed_dev.sh`: applies schema + seeds one tenant and one agent definition for local testing.
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

### LiteLLM routing note

- The LiteLLM config is rendered from `infra/litellm/config.yaml.template` / `config.light.yaml.template` at container start.
- The `default` alias automatically falls back to `fast` when the primary provider errors or times out.
- The same alias-only routing path is used by sync, session, tool-agent, and batch/async examples.
- You can tune the alias caps with `LITELLM_BUDGET_*` and the default tenant cap with `LITELLM_TENANT_BUDGET_TOTAL` in `.env`.
- After changing alias env vars or fallback wiring, restart the `litellm` service (or rerun `bash infra/bootstrap-light.sh`).

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

## US5 - Async Job Lifecycle

Files:
- `examples/us5_async_job_example.py`: submits `POST /api/v1/jobs` and polls `GET /api/v1/jobs/{job_id}` until the job reaches a terminal state.

### Run the async example

```bash
export AGENT_API_KEY="$(grep '^AGENT_API_KEY=' .env | cut -d'=' -f2-)"
export AGENT_ID="00000000-0000-0000-0000-000000000001"
export AGENT_ASYNC_INPUT="Analyze the backlog and return a short triage summary"
export AGENT_TIMEOUT_SECONDS=180
export AGENT_POLL_INTERVAL_SECONDS=2
python examples/us5_async_job_example.py
```

Expected behavior:
- `submit_status: 202`
- the job moves through `pending` / `running`
- final state becomes `completed` with `output` and optional `trace_id`
- if approval-gated tools are introduced later, a paused run will surface as `interrupted` with `pending_approval_id`

### Manual API flow

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"agent_id":"00000000-0000-0000-0000-000000000001","input":"Analyze the backlog"}'

curl -H "X-API-Key: $AGENT_API_KEY" \
  http://localhost:8000/api/v1/jobs/<job-id>
```

### Troubleshooting

If you get `Connection refused`:
- start Docker Desktop / the Docker daemon.
- bootstrap or restart the stack:

```bash
bash infra/bootstrap-light.sh
# or the full stack:
bash infra/bootstrap.sh
```

If you get `HTTP 401`:
- verify `AGENT_API_KEY` matches the value in `.env`.
- rerun `bash examples/us2_seed_dev.sh` to reseed the demo tenant and agent.

If the job stays in `pending`:
- recreate the updated worker service:

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d --force-recreate agent-worker
# or the light stack:
docker compose -f infra/docker-compose.light.yml --env-file .env up -d --force-recreate agent-worker
```

- inspect worker logs:

```bash
docker compose -f infra/docker-compose.yml --env-file .env logs --tail=120 agent-worker
```

## US7 - Trace Review and Replay

Files:
- `examples/us7_trace_replay_example.py`: executes a sync run to capture `trace_id`, then replays via `POST /api/v1/run/replay`.

### Run the US7 example

```bash
export AGENT_API_KEY="$(grep '^AGENT_API_KEY=' .env | cut -d'=' -f2-)"
export AGENT_ID="00000000-0000-0000-0000-000000000001"
export AGENT_TIMEOUT_SECONDS=180
python examples/us7_trace_replay_example.py
```

Optional input overrides:

```bash
export AGENT_US7_INPUT="Summarize the latest production incident in 5 bullets"
export AGENT_US7_REPLAY_INPUT="Re-run with stricter focus on timeline"
python examples/us7_trace_replay_example.py
```

Expected behavior:
- `initial_trace_id` is present from the first `POST /api/v1/run`
- replay call returns `replay_trace_id` and `replay_output`
- in Langfuse UI, you can search for both trace IDs to compare original vs replayed execution

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

## US4 - Code Execution Tool

Files:
- `examples/us4_code_exec_example.py`: runs Python code in two modes — tool-only (default) or full LLM loop (`WITH_LLM=1`).

The tool executes Python code in an **isolated subprocess** with:
- Timeout enforcement (default 30s)
- Output capture and truncation (default 10KB)
- Secret isolation (API keys stripped from subprocess environment)
- Full error visibility (stdout + stderr + exit code)

⚠️ **Safety note**: Code execution is sandboxed but not bulletproof. It's intended for trusted code (LLM-generated with guardrails, not user-supplied arbitrary code).

### Mode 1 — Tool only (no LLM required)

```bash
export CODE_TO_EXECUTE="import math; print(f'Pi = {math.pi}')"
export CODE_EXEC_TIMEOUT_SECONDS=10           # optional, default 30
export CODE_EXEC_MAX_OUTPUT_BYTES=10240       # optional, default 10KB
python examples/us4_code_exec_example.py
```

Expected output:
- `Execution succeeded` with exit code 0 if code ran without errors.
- `=== STDOUT ===` section with the code's output.
- `=== STDERR ===` section if there were warnings/errors (empty if clean).
- Execution time in milliseconds.

### Mode 2 — Full LLM loop

Requires LiteLLM running and a registered API key (same setup as web_search Mode 2).

```bash
export LITELLM_BASE_URL="http://localhost:4000"
export LITELLM_API_KEY="$(grep '^LITELLM_MASTER_KEY=' .env | cut -d'=' -f2-)"  # Use master key locally
export CODE_TASK="Write code to calculate the sum of the first 10 square numbers and print it"
WITH_LLM=1 python examples/us4_code_exec_example.py
```

Expected output:
- LLM generates Python code for the task.
- Tool executes the code in a subprocess.
- LLM receives the execution result and summarizes it.

### Troubleshooting

If you get `code execution failed: code must not be blank`:
- verify `CODE_TO_EXECUTE` is set and not empty.

If you get `code execution failed: code execution timed out`:
- the code is taking longer than `CODE_EXEC_TIMEOUT_SECONDS`.
- increase the timeout: `export CODE_EXEC_TIMEOUT_SECONDS=60`
- or optimize the code to run faster.

If you get `Execution succeeded` but with unexpected output:
- check the `=== STDERR ===` section for warnings from the Python interpreter.
- ensure imports are valid (only stdlib + pre-installed packages available in subprocess).

If Mode 2 fails with `HTTP 401`:
- use the master key as shown above (locally recommended), or register the virtual key as documented in [LiteLLM token setup](#litellm-token-setup).

## US4 - REST Caller Tool

Files:
- `examples/us4_rest_caller_example.py`: calls HTTP APIs in two modes — tool-only (default) or full LLM loop (`WITH_LLM=1`).

The tool supports `GET`, `POST`, `PUT`, `PATCH`, `DELETE` and includes timeout handling + body truncation protection.

### Mode 1 — Tool only (no LLM required)

```bash
export REST_URL="http://localhost:8000/health"
export REST_METHOD="GET"                    # optional, default GET
export REST_TIMEOUT_SECONDS=10               # optional, default 10
export REST_MAX_BODY_BYTES=4096              # optional, default 4096
python examples/us4_rest_caller_example.py
```

Expected output:
- HTTP status and latency (e.g. `HTTP 200 in 35ms`)
- method + URL used
- response body preview

### Mode 2 — Full LLM loop

```bash
export LITELLM_BASE_URL="http://localhost:4000/v1"
export LITELLM_API_KEY="$(grep '^LITELLM_MASTER_KEY=' .env | cut -d'=' -f2-)"
export REST_TASK="Call GET http://localhost:8000/health and summarize whether dependencies are healthy."
WITH_LLM=1 python examples/us4_rest_caller_example.py
```

Expected output:
- LLM emits a tool call for `rest_caller`
- tool executes the HTTP call and returns status/body
- LLM synthesises a final summary

### Troubleshooting

If you get `REST call timed out`:
- increase `REST_TIMEOUT_SECONDS`
- verify target endpoint is reachable

If you get `url must be absolute and start with http:// or https://`:
- provide full URL (e.g. `http://localhost:8000/health`)

If Mode 2 fails with `Connection error`:
- ensure `LITELLM_BASE_URL` is `http://localhost:4000/v1` when running from host terminal
- verify LiteLLM health: `curl -s http://localhost:4000/health`

## US4 - File Operations Tool

Files:
- `examples/us4_file_ops_example.py`: runs sandboxed file operations in two modes — tool-only (default) or full LLM loop (`WITH_LLM=1`).

The tool executes file reads/writes inside a sandbox root directory and blocks path traversal outside that root.

### Mode 1 — Tool only (no LLM required)

```bash
export FILE_OPS_ROOT_DIR="/tmp/2brain_file_ops_example"   # optional
python examples/us4_file_ops_example.py
```

Expected output:
- `make_dir` creates a sandbox subdirectory
- `write_file` writes content under sandbox
- `read_file` returns file content
- `list_dir` shows sandbox entries
- `delete_path` removes the folder recursively

### Mode 2 — Full LLM loop

```bash
export LITELLM_BASE_URL="http://localhost:4000/v1"
export LITELLM_API_KEY="$(grep '^LITELLM_MASTER_KEY=' .env | cut -d'=' -f2-)"
export FILE_OPS_TASK="Create docs/todo.txt with two TODO lines, then read it and summarize"
WITH_LLM=1 python examples/us4_file_ops_example.py
```

Expected output:
- LLM emits a tool call for `file_ops`
- tool performs sandboxed operation and returns structured output
- LLM synthesises a final response from tool output

### Troubleshooting

If you get `path escapes sandbox root`:
- use relative paths (for example `docs/todo.txt`)
- avoid traversal patterns like `../`

If you get `file not found`:
- ensure a write/create step runs before read/delete

If Mode 2 fails with `Connection error`:
- ensure `LITELLM_BASE_URL` is `http://localhost:4000/v1`
- verify LiteLLM health with `curl -s http://localhost:4000/health`

## US4 - Tool-Agent Graph Loop + Tool Spans

Files:
- `examples/us4_tool_agent_graph_example.py`: runs the tool-agent graph in two modes:
  - deterministic local mode (default) with a fake LLM that always calls `code_exec`
  - LiteLLM mode (`WITH_LLM=1`) using real model/tool-calling behavior

This example demonstrates:
- per-agent tool allowlist resolution
- tool call retries/fail handling inside the graph loop
- tool span emission (`args`, `output`, `latency`, `error`) via observability callbacks

### Mode 1 - Deterministic local run

```bash
python examples/us4_tool_agent_graph_example.py
```

Expected output:
- `status: completed`
- one `tool_events` entry for `code_exec`
- one callback span payload in `Tool Spans (Observability Callback)`

### Mode 2 - With LiteLLM

```bash
export LITELLM_BASE_URL="http://localhost:4000/v1"
export LITELLM_API_KEY="$(grep '^LITELLM_MASTER_KEY=' .env | cut -d'=' -f2-)"
export TOOL_AGENT_TASK="Use code_exec to compute the sum of squares from 1 to 5, then answer briefly."
WITH_LLM=1 python examples/us4_tool_agent_graph_example.py
```

Expected behavior:
- model may choose one or more tools from allowlist
- tool calls are executed with retry handling
- each attempt emits a structured tool span in callback output

### Troubleshooting

If mode 2 fails with `Connection error`:
- set `LITELLM_BASE_URL=http://localhost:4000/v1` from host terminal
- confirm LiteLLM is reachable: `curl -s http://localhost:4000/health`

If no tool call occurs in mode 2:
- refine prompt to explicitly require a tool action
- use deterministic mode to validate graph wiring independent of model behavior

