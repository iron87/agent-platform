"""Langfuse callback wiring for LangGraph and LiteLLM observability.

Provides:
- Langfuse trace initialization at execution start
- LangGraph callback handler for tracing all node executions
- Graceful fail-open: if Langfuse unavailable, continue without tracing
- Trace metadata propagation (client_id, agent_id, job_id)
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langfuse.langchain import CallbackHandler

logger = logging.getLogger(__name__)


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
    client_id: str,
    agent_id: str,
    job_id: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Inject trace metadata into LangGraph config.

    Adds metadata that Langfuse can pick up for trace context. The config dict
    is updated in-place and returned for convenience.

    Args:
        config: LangGraph ainvoke config dict
        client_id: Tenant identifier
        agent_id: Agent definition UUID
        job_id: Job/execution record UUID
        session_id: Optional session identifier for conversational mode

    Returns:
        Updated config dict with metadata injected

    Notes:
        - Langfuse extracts metadata from config["metadata"] if present
        - Tag format supports hierarchical organization (e.g., "client:tenant-1")
    """
    if "metadata" not in config:
        config["metadata"] = {}

    config["metadata"].update({
        "client_id": client_id,
        "agent_id": agent_id,
        "job_id": job_id,
        "session_id": session_id or "none",
    })

    if "tags" not in config:
        config["tags"] = []

    config["tags"].extend([
        f"client:{client_id}",
        f"agent:{agent_id}",
        f"job:{job_id}",
    ])

    logger.debug(
        "trace_metadata_injected",
        client_id=client_id,
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
        client_id: str,
        agent_id: str,
        job_id: str,
        session_id: str | None = None,
    ) -> None:
        """Initialize trace context.

        Args:
            settings: Configuration object with Langfuse settings
            client_id: Tenant identifier
            agent_id: Agent definition UUID
            job_id: Execution record UUID
            session_id: Optional session ID for conversational mode
        """
        self.settings = settings
        self.client_id = client_id
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
        self.config["callbacks"] = build_execution_callbacks(self.handler)

        inject_trace_metadata(
            self.config,
            client_id=self.client_id,
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
                client_id=self.client_id,
                job_id=self.job_id,
            )

        # Cleanup (if Langfuse handler has any cleanup logic)
        # Currently Langfuse callback handlers don't require cleanup
        logger.debug(
            "execution_trace_context_closed",
            trace_id=self.trace_id,
            client_id=self.client_id,
        )


__all__ = [
    "create_langfuse_handler",
    "inject_trace_metadata",
    "build_execution_callbacks",
    "extract_trace_id",
    "ExecutionTraceContext",
]
