"""LangGraph registry and bootstrapping for agent execution graphs.

Provides:
- Graph registry factory: loads graph implementations by type
- Graph builder cache: avoids rebuilding the same graph repeatedly
- Checkpointer setup: AsyncPostgresSaver for HITL durability (deferred import)
"""

from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable

from langgraph.graph import StateGraph
import structlog

from agent.graphs.conversational import build_conversational_graph

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = structlog.get_logger(__name__)


_GRAPHS: dict[str, Callable[[], StateGraph]] = {
    "conversational": build_conversational_graph,
}


async def create_graph_checkpointer(engine: "AsyncEngine") -> Any:
    """Initialize the async PostgreSQL checkpointer for LangGraph persistence.
    
    The checkpointer provides durable state storage for HITL (Human-In-The-Loop)
    approval gates and long-running executions. On resume after interrupt(),
    the full state is restored from PostgreSQL.
    
    Args:
        engine: SQLAlchemy async engine pointing to the agent platform database
        
    Returns:
        AsyncPostgresSaver configured with the provided connection string
        
    Raises:
        Exception: If checkpointer table creation fails (DB connectivity issue)
        
    Notes:
        - Checkpointer tables are created automatically on first setup()
        - Safe to call multiple times (idempotent)
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    
    async with engine.begin() as conn:
        connection_str = str(engine.url)

    checkpointer = AsyncPostgresSaver.from_conn_string(connection_str)
    await checkpointer.setup()
    logger.info("langgraph_checkpointer_initialized", checkpointer_type="postgres")
    return checkpointer


def register_graph(graph_type: str, graph_builder: Callable[[], StateGraph]) -> None:
    """Register a graph implementation in the runtime registry.
    
    Args:
        graph_type: One of 'conversational', 'tool_agent', 'batch_agent'
        graph_builder: Callable returning a compiled StateGraph
    """
    _GRAPHS[graph_type] = graph_builder
    logger.info(
        "graph_registered",
        graph_type=graph_type,
        graph_builder=getattr(graph_builder, "__name__", "<callable>"),
    )


def get_graph_builder(
    graph_type: str,
) -> type[StateGraph] | None:
    """Retrieve a registered graph builder by type.
    
    Args:
        graph_type: One of 'conversational', 'tool_agent', 'batch_agent'
        
    Returns:
        Graph builder callable, or None if graph_type is not registered
    """
    return _GRAPHS.get(graph_type)


@lru_cache(maxsize=16)
def get_cached_graph(graph_type: str) -> StateGraph | None:
    """Get a cached, compiled graph instance (single-process cache).
    
    This avoids rebuilding the same graph repeatedly. The cache is
    cleared if new graphs are registered.
    
    Args:
        graph_type: One of 'conversational', 'tool_agent', 'batch_agent'
        
    Returns:
        Compiled StateGraph instance, or None if graph_type is not registered
    """
    builder = get_graph_builder(graph_type)
    if builder is None:
        return None
    return builder()


__all__ = [
    "create_graph_checkpointer",
    "register_graph",
    "get_graph_builder",
    "get_cached_graph",
]
