"""Langfuse callback wiring for LangGraph and LiteLLM observability.

Provides:
 Langfuse trace initialization at execution start
 LangGraph callback handler for tracing all node executions
 Graceful fail-open: if Langfuse unavailable, continue without tracing
 Trace metadata propagation (tenant_id, agent_id, job_id)
"""

from typing import TYPE_CHECKING, Any
import structlog
import json
from time import perf_counter

if TYPE_CHECKING:
    from langfuse.langchain import CallbackHandler

logger = structlog.get_logger(__name__)


def fallback_trace_id(execution_id: str) -> str:
    """Return a deterministic local trace id when Langfuse is unavailable."""
    return f"local-{execution_id}"

def _serialize_trace_value(value: Any, *, max_len: int = 4000) -> str:
    """Serialize a value for tracing payloads with bounded size."""
    try:
        rendered = json.dumps(value, default=str)
    except TypeError:
        rendered = str(value)

    if len(rendered) <= max_len:
        return rendered
    return rendered[:max_len] + "...<truncated>"


def create_langfuse_handler(
    settings: Any,
) -> "CallbackHandler | None":
    """Create Langfuse callback handler with fail-open behavior.

    If Langfuse is unreachable or misconfigured, logs warning and returns None.
    When None is returned, execution proceeds without tracing.

    Args:
        settings: Configuration object with Langfuse connection details:
            - LANGFUSE_PUBLIC_KEY: Public API key
            - LANGFUSE_SECRET_KEY: Secret API key
            - LANGFUSE_HOST: API endpoint (default "http://langfuse:3000")

    Returns:
        CallbackHandler instance, or None if initialization failed
    """
    if not bool(getattr(settings, "LANGFUSE_ENABLED", True)):
        logger.warning(
            "langfuse_disabled_fail_open",
            message="LANGFUSE_ENABLED=false; continuing without external tracing",
        )
        return None

    try:
        from langfuse.langchain import CallbackHandler

        handler = CallbackHandler(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )

        logger.info(
            "langfuse_handler_initialized",
            host=settings.LANGFUSE_HOST,
        )

        return handler

    except ImportError:
        logger.error(
            "langfuse_import_failed",
            message="langfuse-python package not installed; tracing disabled",
        )
        return None

    except Exception as e:
        logger.warning(
            "langfuse_handler_creation_failed",
            error_type=type(e).__name__,
            error_message=str(e),
            message="Proceeding without Langfuse tracing",
        )
        return None


def inject_trace_metadata(
    config: dict[str, Any],
    *,
    tenant_id: str,
    agent_id: str,
    job_id: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Inject trace metadata into LangGraph config.

    Adds metadata that Langfuse can pick up for trace context. The config dict
    is updated in-place and returned for convenience.

    Args:
        config: LangGraph ainvoke config dict
        tenant_id: Tenant identifier
        agent_id: Agent definition UUID
        job_id: Job/execution record UUID
        session_id: Optional session identifier for conversational mode

    Returns:
        Updated config dict with metadata injected

    Notes:
        - Langfuse extracts metadata from config["metadata"] if present
        - Tag format supports hierarchical organization (e.g., "tenant:team-1")
    """
    if "metadata" not in config:
        config["metadata"] = {}

    config["metadata"].update({
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "job_id": job_id,
        "session_id": session_id or "none",
    })

    if "tags" not in config:
        config["tags"] = []

    config["tags"].extend([
        f"tenant:{tenant_id}",
        f"agent:{agent_id}",
        f"job:{job_id}",
    ])

    logger.debug(
        "trace_metadata_injected",
        tenant_id=tenant_id,
        agent_id=agent_id,
        job_id=job_id,
    )

    return config


def build_execution_callbacks(
    handler: "CallbackHandler | None",
) -> list[Any]:
    """Build callback list for graph execution.

    If handler is None (Langfuse unavailable), returns empty list.
    Graph will execute normally, just without tracing.

    Args:
        handler: Langfuse CallbackHandler or None

    Returns:
        List of callbacks to pass to graph.ainvoke(..., config={"callbacks": [...]})
    """
    if handler is None:
        return []

    return [handler]


def extract_trace_id(handler: "CallbackHandler | None") -> str | None:
    """Extract Langfuse trace ID from callback handler (if available).

    Args:
        handler: Langfuse CallbackHandler or None

    Returns:
        Trace ID string, or None if handler is None or trace not created yet
    """
    if handler is None:
        return None

    try:
        # Langfuse CallbackHandler stores trace_id after first LLM call
        return getattr(handler, "trace_id", None)
    except AttributeError:
        return None

def emit_tool_call_span(
    callbacks: list[Any] | None,
    *,
    tool_name: str,
    args: dict[str, Any],
    output: Any,
    error: str | None,
    attempt: int,
    started_at: float | None = None,
) -> None:
    """Emit tool call span data to trace callbacks and structured logs.

    The callback contract is intentionally loose to support different callback
    implementations. If a callback exposes `on_custom_event`, this function
    publishes a `tool_call` event payload.
    """
    elapsed_ms = 0
    if started_at is not None:
        elapsed_ms = int((perf_counter() - started_at) * 1000)

    payload = {
        "tool_name": tool_name,
        "attempt": attempt,
        "latency_ms": elapsed_ms,
        "args": _serialize_trace_value(args),
        "output": _serialize_trace_value(output) if error is None else None,
        "error": error,
        "ok": error is None,
    }

    for callback in callbacks or []:
        on_custom_event = getattr(callback, "on_custom_event", None)
        if callable(on_custom_event):
            try:
                on_custom_event(name="tool_call", data=payload)
            except Exception:
                # Tracing should never break runtime execution.
                logger.debug("tool_call_callback_failed", callback_type=type(callback).__name__)

    logger.info(
        "tool_call_span",
        tool_name=tool_name,
        attempt=attempt,
        latency_ms=elapsed_ms,
        ok=error is None,
        error=error,
    )


def emit_approval_event(
    callbacks: list[Any] | None,
    *,
    event_name: str,
    approval_id: str,
    job_id: str,
    tool_name: str,
    status: str,
    reviewer_id: str | None = None,
    reason: str | None = None,
) -> None:
    """Emit approval lifecycle events to callbacks and structured logs."""
    payload = {
        "approval_id": approval_id,
        "job_id": job_id,
        "tool_name": tool_name,
        "status": status,
        "reviewer_id": reviewer_id,
        "reason": reason,
    }

    for callback in callbacks or []:
        on_custom_event = getattr(callback, "on_custom_event", None)
        if callable(on_custom_event):
            try:
                on_custom_event(name=event_name, data=payload)
            except Exception:
                logger.debug("approval_callback_failed", callback_type=type(callback).__name__)

    logger.info(
        "approval_event",
        event_name=event_name,
        approval_id=approval_id,
        job_id=job_id,
        tool_name=tool_name,
        status=status,
        reviewer_id=reviewer_id,
    )


class ExecutionTraceContext:
    """Context manager for traced execution with automatic resource cleanup.

    Usage:
        async with ExecutionTraceContext(settings, job_id=job_id) as ctx:
            result = await graph.ainvoke(payload, config=ctx.config)
            return {"output": result, "trace_id": ctx.trace_id}

    Notes:
        - Automatically injects trace metadata into config
        - Handles Langfuse handler creation/cleanup
        - Gracefully degrades if Langfuse unavailable
    """

    def __init__(
        self,
        settings: Any,
        *,
        tenant_id: str,
        agent_id: str,
        job_id: str,
        session_id: str | None = None,
    ) -> None:
        """Initialize trace context.

        Args:
            settings: Configuration object with Langfuse settings
            tenant_id: Tenant identifier
            agent_id: Agent definition UUID
            job_id: Execution record UUID
            session_id: Optional session ID for conversational mode
        """
        self.settings = settings
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.job_id = job_id
        self.session_id = session_id

        self.handler: "CallbackHandler | None" = None
        self.config: dict[str, Any] = {
            "configurable": {"thread_id": str(job_id)}
        }
        self.trace_id: str | None = None

    async def __aenter__(self) -> "ExecutionTraceContext":
        """Enter async context manager."""
        self.handler = create_langfuse_handler(self.settings)
        if self.handler is None:
            logger.warning(
                "langfuse_unavailable_fail_open",
                tenant_id=self.tenant_id,
                job_id=self.job_id,
                message="Proceeding without Langfuse tracing",
            )
        self.config["callbacks"] = build_execution_callbacks(self.handler)

        inject_trace_metadata(
            self.config,
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            job_id=self.job_id,
            session_id=self.session_id,
        )

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        # Try to extract trace ID before cleanup
        self.trace_id = extract_trace_id(self.handler)

        if exc_type is not None:
            logger.error(
                "execution_trace_context_error",
                error_type=exc_type.__name__,
                tenant_id=self.tenant_id,
                job_id=self.job_id,
            )

        # Cleanup (if Langfuse handler has any cleanup logic)
        # Currently Langfuse callback handlers don't require cleanup
        logger.debug(
            "execution_trace_context_closed",
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
        )


__all__ = [
    "create_langfuse_handler",
    "fallback_trace_id",
    "inject_trace_metadata",
    "build_execution_callbacks",
    "emit_tool_call_span",
    "emit_approval_event",
    "extract_trace_id",
    "ExecutionTraceContext",
]
