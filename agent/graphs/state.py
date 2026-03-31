"""Shared LangGraph state schema for all agent types."""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Unified state schema for all agent graph types (conversational, tool_agent, batch).
    
    This TypedDict is the canonical state interface for:
    - Conversational agent: multi-turn dialog with semantic memory lookup
    - Tool agent: ReAct loop with tool selection and HITL approval gates
    - Batch agent: pipeline execution with result aggregation
    
    The state is persisted to AsyncPostgresSaver checkpointer for durability.
    """

    # Input payload
    client_id: str
    """Tenant identifier for namespace isolation (e.g., Redis keys, Qdrant collections)"""

    job_id: str
    """Execution record ID from `jobs` table; used for tracing and approval linkage"""

    session_id: str | None
    """Non-null for conversational mode; identifies persistent turn history in Redis"""

    input: str
    """User prompt or task input; 1-131072 characters"""

    # Conversation (message history with LangGraph reducer)
    messages: Annotated[list, add_messages]
    """LangGraph-managed conversation history with automatic deduplication.
    
    add_messages reducer ensures:
    - Consecutive duplicate messages are coalesced
    - New messages with same ID replace old messages
    - Final list is always most recent state
    """

    # Tool execution state
    pending_tool: str | None
    """Name of the tool awaiting execution (e.g., 'web_search', 'code_exec')"""

    tool_args: dict[str, Any] | None
    """Arguments the agent proposes to pass to pending_tool"""

    tool_result: str | None
    """Output from tool execution; set by tool node, consumed by agent node"""

    tool_events: list[dict[str, Any]] | None
    """Structured summary of tool execution attempts for the current run."""

    output: str | None
    """Final model response text for the current execution."""

    # Control flow
    status: str
    """Execution status: 'running' | 'interrupted' | 'completed' | 'failed'
    
    Transitions:
    - 'running' → 'completed' (normal termination)
    - 'running' → 'failed' (error or rejection)
    - 'running' → 'interrupted' (HITL approval gate hit)
    - 'interrupted' → 'running' (approval granted, resumed)
    - 'interrupted' → 'failed' (approval rejected or timeout)
    """

    approved: bool | None
    """Set by HITL decision node after interrupt() decision retrieved.
    
    Meanings:
    - None: no approval gate encountered yet
    - True: tool was approved, execution should continue
    - False: tool was rejected, execution should gracefully error
    """

    error: str | None
    """Error message if status='failed'; describes why execution stopped"""

    # Runtime-only helpers injected by service before graph invocation
    _llm_client: Any | None
    _model_alias: str | None
    _system_prompt: str | None
    _agent_definition: dict[str, Any] | None
    _tool_registry: dict[str, Any] | None
    _trace_callbacks: list[Any] | None
    _max_tool_steps: int | None
    _max_tool_retries: int | None
