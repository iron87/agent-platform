from __future__ import annotations

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_pyproject_has_required_metadata_and_dependency_groups() -> None:
    data = tomllib.loads(_read("pyproject.toml"))

    project = data["project"]
    assert project["name"] == "2brain-platform"
    assert project["requires-python"] == ">=3.12"

    deps = set(project["dependencies"])
    assert any(dep.startswith("fastapi") for dep in deps)
    assert any(dep.startswith("bcrypt") for dep in deps)
    assert any(dep.startswith("pydantic") for dep in deps)
    assert any(dep.startswith("langgraph") for dep in deps)

    optional = project["optional-dependencies"]
    dev = set(optional["dev"])
    assert any(dep.startswith("pytest") for dep in dev)
    assert any(dep.startswith("ruff") for dep in dev)
    assert any(dep.startswith("mypy") for dep in dev)


def test_pyproject_package_discovery_is_scoped() -> None:
    data = tomllib.loads(_read("pyproject.toml"))
    find_cfg = data["tool"]["setuptools"]["packages"]["find"]

    assert find_cfg["where"] == ["."]
    assert "agent*" in find_cfg["include"]
    assert "api*" in find_cfg["include"]
    assert "worker*" in find_cfg["include"]


def test_makefile_has_bootstrap_test_and_run_targets() -> None:
    makefile = _read("Makefile")

    required_targets = [
        "bootstrap:",
        "run:",
        "run-api:",
        "run-worker:",
        "test:",
        "test-unit:",
        "test-integration:",
        "lint:",
        "format:",
    ]

    for target in required_targets:
        assert target in makefile


def test_ignore_files_have_critical_patterns() -> None:
    gitignore = _read(".gitignore")
    dockerignore = _read(".dockerignore")

    for expected in ["__pycache__/", "*.pyc", ".venv/", ".env", ".DS_Store"]:
        assert expected in gitignore

    for expected in [".git/", "__pycache__/", "*.pyc", ".env", "*.log*"]:
        assert expected in dockerignore


def test_env_example_contains_documented_required_keys() -> None:
    env_example = _read("infra/.env.example")

    required_keys = [
        "ENV=",
        "AGENT_API_KEY=",
        "DATABASE_URL=",
        "REDIS_URL=",
        "QDRANT_URL=",
        "LITELLM_BASE_URL=",
        "LITELLM_MASTER_KEY=",
        "LOCAL_LLM_API_BASE=",
        "LOCAL_DEFAULT_MODEL=",
        "LOCAL_FAST_MODEL=",
        "LOCAL_EMBEDDING_MODEL=",
        "LANGFUSE_PUBLIC_KEY=",
        "LANGFUSE_SECRET_KEY=",
        "CLICKHOUSE_PASSWORD=",
        "JOB_TIMEOUT_SECONDS=",
    ]

    for key in required_keys:
        assert key in env_example


def test_litellm_template_defines_required_aliases() -> None:
    template = _read("infra/litellm/config.yaml.template")

    assert "model_name: default" in template
    assert "model_name: fast" in template
    assert "model_name: embedding" in template
    assert "fallbacks:" in template
    assert 'default: ["fast"]' in template
    assert "${LOCAL_LLM_API_BASE}" in template
    assert "${LOCAL_DEFAULT_MODEL}" in template


def test_compose_stack_defines_required_phase_one_services() -> None:
    compose = _read("infra/docker-compose.yml")

    for service in [
        "caddy:",
        "postgres:",
        "redis:",
        "qdrant:",
        "litellm:",
        "langfuse:",
        "clickhouse:",
        "minio:",
        "agent-api:",
        "agent-worker:",
    ]:
        assert service in compose


def test_bootstrap_script_contains_secret_startup_and_wait_logic() -> None:
    bootstrap = _read("infra/bootstrap.sh")

    assert bootstrap.startswith("#!/usr/bin/env bash")
    assert "openssl rand -hex 16" in bootstrap
    assert 'docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d' in bootstrap
    assert "wait_for_http" in bootstrap
    assert "Bootstrap complete" in bootstrap


def test_caddyfile_routes_traffic_to_agent_api_with_tls() -> None:
    caddyfile = _read("infra/caddy/Caddyfile")

    assert "tls internal" in caddyfile
    assert "reverse_proxy agent-api:8000" in caddyfile
    assert "{$CADDY_HOST:localhost}" in caddyfile


def test_phase_two_foundation_artifacts_exist() -> None:
    config = _read("api/config.py")
    db = _read("api/db.py")
    deps = _read("api/deps.py")
    logging_setup = _read("api/logging.py")
    main = _read("api/main.py")
    run_models = _read("api/models/run.py")
    job_models = _read("api/models/jobs.py")
    approval_models = _read("api/models/approvals.py")
    error_models = _read("api/models/errors.py")
    migration = _read("infra/migrations/001_initial_schema.sql")

    assert "class Settings(BaseSettings)" in config
    assert "def get_settings()" in config
    assert "class ClientsRepository" in db
    assert "async def get_db_session()" in db
    assert "class TenantContext" in deps
    assert "async def get_current_tenant" in deps
    assert "structlog.processors.JSONRenderer" in logging_setup
    assert "def create_app(" in main
    assert "RunRequest" in run_models
    assert "JobStatus" in job_models
    assert "ApprovalDecision" in approval_models
    assert "class ErrorResponse" in error_models
    for table_name in [
        "CREATE TABLE IF NOT EXISTS clients",
        "CREATE TABLE IF NOT EXISTS agent_definitions",
        "CREATE TABLE IF NOT EXISTS jobs",
        "CREATE TABLE IF NOT EXISTS approval_requests",
        "CREATE TABLE IF NOT EXISTS client_policies",
    ]:
        assert table_name in migration


def test_phase_two_foundation_layer_2_artifacts_exist() -> None:
    """Verify T016, T017, T018 artifacts are created with expected signatures."""
    state_module = _read("agent/graphs/state.py")
    graphs_init = _read("agent/graphs/__init__.py")
    llm_module = _read("agent/llm.py")
    session_store = _read("agent/session_store.py")

    # T016: AgentState TypedDict and graph registry
    assert "class AgentState(TypedDict)" in state_module
    assert "client_id: str" in state_module
    assert "messages: Annotated[list, add_messages]" in state_module
    assert "pending_tool: str | None" in state_module

    # T016: Graph registry and checkpointer
    assert "async def create_graph_checkpointer" in graphs_init
    assert "def register_graph" in graphs_init
    assert "def get_graph_builder" in graphs_init
    assert "def get_cached_graph" in graphs_init
    assert "_GRAPHS: dict[str, type[StateGraph]]" in graphs_init

    # T017: LiteLLM client wrapper
    assert "class LiteLLMClient" in llm_module
    assert "VALID_ALIASES = " in llm_module
    assert '"default", "fast", "embedding"' in llm_module
    assert "async def create_completion" in llm_module
    assert "async def create_embedding" in llm_module
    assert "class LiteLLMClientError" in llm_module

    # T018: Redis session store
    assert "class SessionTurn" in session_store
    assert "class SessionMetadata" in session_store
    assert "class RedisSessionStore" in session_store
    assert "async def create_session" in session_store
    assert "async def append_turn" in session_store
    assert "async def load_turns" in session_store
    assert "def _turns_key" in session_store
    assert "def _meta_key" in session_store
    assert "{client_id}:session:{session_id}:turns" in session_store


def test_phase_two_foundation_layer_3_artifacts_exist() -> None:
    """Verify T019, T020, T021, T022 artifacts are created with expected signatures."""
    memory_module = _read("agent/memory.py")
    policy_module = _read("agent/policy.py")
    observability_module = _read("agent/observability.py")
    queue_module = _read("worker/queue.py")

    # T019: Semantic memory abstraction
    assert "class MemoryScope" in memory_module
    assert "class MemoryRecord" in memory_module
    assert "class SemanticMemoryStore(Protocol)" in memory_module
    assert "class Mem0MemoryStore" in memory_module
    assert "async def upsert_fact" in memory_module
    assert "async def search" in memory_module
    assert "async def delete" in memory_module
    assert "{client_id}_memory" in memory_module

    # T020: Policy registry with hot-reload
    assert "def initialize_policies" in policy_module
    assert "def start_hot_reload_loop" in policy_module
    assert "def get_rails" in policy_module
    assert "async def apply_policy" in policy_module
    assert "_registry: dict" in policy_module
    assert "_registry_lock = threading.Lock()" in policy_module
    assert "interval_seconds: int = 20" in policy_module

    # T021: Langfuse observability
    assert "def create_langfuse_handler" in observability_module
    assert "def inject_trace_metadata" in observability_module
    assert "def build_execution_callbacks" in observability_module
    assert "def extract_trace_id" in observability_module
    assert "class ExecutionTraceContext" in observability_module
    assert "async def __aenter__" in observability_module
    assert "async def __aexit__" in observability_module
    assert "fail-open" in observability_module or "fail_open" in observability_module

    # T022: rq Queue factory
    assert "def create_queue" in queue_module
    assert "def enqueue_job" in queue_module
    assert "def get_job_status" in queue_module
    assert "def cancel_job" in queue_module
    assert "class JobCallbackBridge" in queue_module
    assert "class QueueUnavailableError" in queue_module
    assert "Retry(" in queue_module
    assert "result_ttl=86400" in queue_module
