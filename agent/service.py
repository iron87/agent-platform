"""Shared agent service orchestrator for sync/session/async execution modes.

Central orchestration point that ties together:
- Graph selection (ConversationalGraph, ToolAgentGraph, BatchAgentGraph)
- Semantic memory (Mem0)
- Session history (Redis)
- Policy enforcement (NeMo Guardrails)
- LLM interaction (LiteLLM)
- Observability (Langfuse tracing)
- Database operations (agent definitions, jobs, clients)

Provides three execution modes:
  1. Sync (ExecutionMode.SYNC): immediate response, single turn
  2. Session (ExecutionMode.SESSION): preserves turn history, returns output + session_id
  3. Async (ExecutionMode.ASYNC): enqueues to job queue, returns job_id for polling
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """Execution mode for agent invocation."""

    SYNC = "sync"
    """Synchronous: immediate response, single interaction"""

    SESSION = "session"
    """Session-based: preserves turn history, supports multi-turn conversations"""

    ASYNC = "async"
    """Asynchronous: enqueues to job queue for background processing"""


@dataclass(frozen=True)
class ExecutionRequest:
    """Unified request for agent execution across all modes.

    Attributes:
        client_id: Tenant identifier (UUID)
        agent_id: Agent definition identifier (UUID)
        input: User prompt or task input
        mode: Execution mode (sync, session, async)
        session_id: Optional, required for SESSION mode
        metadata: Optional request metadata
    """

    client_id: str
    agent_id: str
    input: str
    mode: ExecutionMode
    session_id: str | None = None
    metadata: dict[str, Any] | None = None

    def validate(self) -> None:
        """Validate request integrity.

        Raises:
            ValueError: If request is invalid for the given mode
        """
        if self.mode == ExecutionMode.SESSION and not self.session_id:
            raise ValueError("session_id is required for SESSION mode")

        if not self.input or len(self.input) < 1:
            raise ValueError("input cannot be empty")

        if len(self.input) > 131072:
            raise ValueError("input cannot exceed 131072 characters")


@dataclass(frozen=True)
class ExecutionResult:
    """Unified result for agent execution across all modes.

    Attributes:
        output: Generated response from the agent
        trace_id: Langfuse trace ID (if tracing enabled)
        session_id: Optional session ID for conversational mode
        job_id: Optional job ID for async mode
        execution_time_ms: Wall-clock execution time
    """

    output: str
    trace_id: str | None
    session_id: str | None = None
    job_id: str | None = None
    execution_time_ms: int | None = None


class AgentService:
    """Unified orchestration service for agent execution.

    Coordinates graph selection, memory/policy/tracing setup, and execution
    across sync/session/async modes. Implements fail-open for optional services
    (Langfuse, Mem0, policy) to ensure core functionality persists.

    Usage:
        service = AgentService(
            agent_repo=agents_repo,
            jobs_repo=jobs_repo,
            session_store=session_store,
            memory_store=memory_store,
            llm_client=llm_client,
            settings=settings,
        )

        result = await service.execute(
            ExecutionRequest(
                client_id="tenant-1",
                agent_id="agent-uuid",
                input="Hello, agent!",
                mode=ExecutionMode.SYNC,
            )
        )
        return {"output": result.output, "trace_id": result.trace_id}
    """

    def __init__(
        self,
        agent_repo: Any,
        jobs_repo: Any,
        session_store: Any,
        memory_store: Any,
        llm_client: Any,
        settings: Any,
        graph_factory: Any | None = None,
        queue_factory: Any | None = None,
    ) -> None:
        """Initialize agent service with all required dependencies.

        Args:
            agent_repo: AgentDefinitionsRepository for agent lookup
            jobs_repo: JobsRepository for updating job status
            session_store: RedisSessionStore for turn history
            memory_store: SemanticMemoryStore (Mem0 or mock)
            llm_client: LiteLLMClient for LLM calls
            settings: Runtime configuration (env vars)
            graph_factory: Graph factory/registry (default: agent.graphs module)
            queue_factory: rq queue factory (default: worker.queue module)
        """
        self.agent_repo = agent_repo
        self.jobs_repo = jobs_repo
        self.session_store = session_store
        self.memory_store = memory_store
        self.llm_client = llm_client
        self.settings = settings
        self.graph_factory = graph_factory
        self.queue_factory = queue_factory

        logger.info("agent_service_initialized")

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute agent in the requested mode.

        Routes to sync/session/async handlers based on mode.

        Args:
            request: ExecutionRequest with agent_id, input, mode, etc.

        Returns:
            ExecutionResult with output, trace_id, and mode-specific fields

        Raises:
            ValueError: If request is invalid
            Exception: If execution fails (propagated from graph/LLM)
        """
        request.validate()

        logger.info(
            "execution_started",
            client_id=request.client_id,
            agent_id=request.agent_id,
            mode=request.mode,
        )

        try:
            if request.mode == ExecutionMode.SYNC:
                return await self._execute_sync(request)
            elif request.mode == ExecutionMode.SESSION:
                return await self._execute_session(request)
            elif request.mode == ExecutionMode.ASYNC:
                return await self._execute_async(request)
            else:
                raise ValueError(f"Unknown execution mode: {request.mode}")

        except Exception as e:
            logger.error(
                "execution_failed",
                client_id=request.client_id,
                agent_id=request.agent_id,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    async def _execute_sync(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute in synchronous mode (immediate response, single turn).

        Flow:
        1. Load agent definition
        2. Select graph and compile
        3. Initialize tracing context
        4. Apply input policy (optional)
        5. Execute graph
        6. Apply output policy (optional)
        7. Return output + trace_id (no session persistence)
        """
        from datetime import datetime, timezone

        start_time = datetime.now(timezone.utc)

        # Load agent definition
        agent_def = await self.agent_repo.get_by_id(request.agent_id)
        if not agent_def:
            raise ValueError(f"Agent not found: {request.agent_id}")

        # Select graph
        graph = self._get_graph(agent_def["graph_type"])
        if graph is None:
            raise ValueError(f"Graph type not registered: {agent_def['graph_type']}")

        # Prepare execution state
        state = {
            "client_id": request.client_id,
            "job_id": request.agent_id,  # Use agent_id as pseudo-job in sync mode
            "session_id": None,
            "input": request.input,
            "messages": [],
            "pending_tool": None,
            "tool_args": None,
            "tool_result": None,
            "status": "running",
            "approved": None,
            "error": None,
        }

        # Apply input policy (optional, fail-open)
        processed_input = request.input
        try:
            from agent.policy import get_rails, apply_policy

            rails = get_rails(request.client_id)
            if rails:
                processed_input, _ = await apply_policy(rails, request.input)
                state["input"] = processed_input
        except Exception as e:
            logger.warning("policy_application_failed_sync", error=str(e))

        # Execute graph
        try:
            from agent.observability import ExecutionTraceContext

            async with ExecutionTraceContext(
                self.settings,
                client_id=request.client_id,
                agent_id=request.agent_id,
                job_id=str(request.agent_id),
            ) as trace_ctx:
                result = await graph.ainvoke(state, config=trace_ctx.config)
                trace_id = trace_ctx.trace_id

        except Exception as e:
            logger.error("graph_execution_failed_sync", error=str(e))
            raise

        # Apply output policy (optional, fail-open)
        output = result.get("output", "")
        try:
            from agent.policy import get_rails, apply_policy

            rails = get_rails(request.client_id)
            if rails:
                output, _ = await apply_policy(rails, output)
        except Exception as e:
            logger.warning("policy_application_failed_output", error=str(e))

        end_time = datetime.now(timezone.utc)
        execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

        logger.info(
            "sync_execution_completed",
            client_id=request.client_id,
            agent_id=request.agent_id,
            execution_time_ms=execution_time_ms,
        )

        return ExecutionResult(
            output=output,
            trace_id=trace_id,
            execution_time_ms=execution_time_ms,
        )

    async def _execute_session(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute in session mode (preserves turn history across invocations).

        Flow:
        1. Load agent definition
        2. Load session history from Redis
        3. Select graph
        4. Inject session context into state
        5. Execute graph
        6. Append user turn + response turn to session history
        7. Return output + trace_id + session_id
        """
        from agent.session_store import SessionTurn
        from datetime import datetime, timezone

        start_time = datetime.now(timezone.utc)

        if not request.session_id:
            raise ValueError("session_id required for SESSION mode")

        # Load agent definition
        agent_def = await self.agent_repo.get_by_id(request.agent_id)
        if not agent_def:
            raise ValueError(f"Agent not found: {request.agent_id}")

        # Load session history
        session_turns = await self.session_store.load_turns(
            client_id=request.client_id,
            session_id=request.session_id,
        )

        # Build message history
        messages = [
            {
                "role": turn.role,
                "content": turn.content,
            }
            for turn in session_turns
        ]

        # Prepare execution state
        state = {
            "client_id": request.client_id,
            "job_id": request.session_id,  # Use session_id as pseudo-job
            "session_id": request.session_id,
            "input": request.input,
            "messages": messages,
            "pending_tool": None,
            "tool_args": None,
            "tool_result": None,
            "status": "running",
            "approved": None,
            "error": None,
        }

        # Select and execute graph
        graph = self._get_graph(agent_def["graph_type"])
        if graph is None:
            raise ValueError(f"Graph type not registered: {agent_def['graph_type']}")

        try:
            from agent.observability import ExecutionTraceContext

            async with ExecutionTraceContext(
                self.settings,
                client_id=request.client_id,
                agent_id=request.agent_id,
                job_id=request.session_id,
                session_id=request.session_id,
            ) as trace_ctx:
                result = await graph.ainvoke(state, config=trace_ctx.config)
                trace_id = trace_ctx.trace_id

        except Exception as e:
            logger.error("graph_execution_failed_session", error=str(e))
            raise

        # Extract output
        output = result.get("output", "")

        # Append turns to session history
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        await self.session_store.append_turn(
            client_id=request.client_id,
            session_id=request.session_id,
            turn=SessionTurn(role="user", content=request.input, timestamp=now),
        )
        await self.session_store.append_turn(
            client_id=request.client_id,
            session_id=request.session_id,
            turn=SessionTurn(role="assistant", content=output, timestamp=now),
        )

        end_time = datetime.now(timezone.utc)
        execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

        logger.info(
            "session_execution_completed",
            client_id=request.client_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
            execution_time_ms=execution_time_ms,
        )

        return ExecutionResult(
            output=output,
            trace_id=trace_id,
            session_id=request.session_id,
            execution_time_ms=execution_time_ms,
        )

    async def _execute_async(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute in async mode (enqueue to background queue).

        Flow:
        1. Create job record in PostgreSQL (status=pending)
        2. Enqueue to rq queue
        3. Return job_id immediately (caller polls for results)

        The actual execution happens in worker/tasks.py via rq worker.
        """
        from uuid import uuid4
        from datetime import datetime, timezone

        job_id = str(uuid4())
        now = datetime.now(timezone.utc)

        # Create job record in PostgreSQL
        job_record = {
            "id": job_id,
            "client_id": request.client_id,
            "agent_id": request.agent_id,
            "session_id": request.session_id,
            "input_payload": request.metadata or {},
            "status": "pending",
            "result": None,
            "error": None,
            "trace_id": None,
            "rq_job_id": None,
            "attempts": 0,
            "mode": request.mode.value,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
        }

        job_id_created = await self.jobs_repo.create(job_record)

        # Enqueue to rq queue (if queue factory available)
        rq_job_id = None
        if self.queue_factory:
            try:
                queue = self.queue_factory.create_queue(self.settings.REDIS_URL)
                job = self.queue_factory.enqueue_job(
                    queue,
                    "worker.tasks.run_agent_job",
                    {
                        "client_id": request.client_id,
                        "agent_id": request.agent_id,
                        "input": request.input,
                        "session_id": request.session_id,
                        "job_id": job_id_created,
                    },
                    job_id=job_id_created,
                    client_id=request.client_id,
                    timeout_seconds=self.settings.JOB_TIMEOUT_SECONDS,
                )
                rq_job_id = job.id

                # Update job record with rq_job_id
                await self.jobs_repo.update_rq_job_id(job_id_created, rq_job_id)

            except Exception as e:
                logger.warning(
                    "async_enqueue_failed",
                    job_id=job_id_created,
                    error=str(e),
                )
                # Continue anyway; job is in pending state for manual processing

        logger.info(
            "async_execution_enqueued",
            client_id=request.client_id,
            agent_id=request.agent_id,
            job_id=job_id_created,
            rq_job_id=rq_job_id,
        )

        return ExecutionResult(
            output="",  # Async mode has no immediate output
            trace_id=None,  # Trace_id will be captured during job execution
            job_id=job_id_created,
            execution_time_ms=0,
        )

    def _get_graph(self, graph_type: str) -> Any | None:
        """Get compiled graph by type from registry.

        Args:
            graph_type: One of "conversational", "tool_agent", "batch_agent"

        Returns:
            Compiled StateGraph, or None if not registered
        """
        if self.graph_factory is None:
            logger.warning("graph_factory_not_available")
            return None

        try:
            graph = self.graph_factory.get_cached_graph(graph_type)
            return graph
        except Exception as e:
            logger.error(
                "graph_retrieval_failed",
                graph_type=graph_type,
                error=str(e),
            )
            return None


__all__ = [
    "ExecutionMode",
    "ExecutionRequest",
    "ExecutionResult",
    "AgentService",
]
