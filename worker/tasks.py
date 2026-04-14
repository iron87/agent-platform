from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Mapping

import redis.asyncio as redis
import structlog

from agent.llm import LiteLLMClient
from agent.memory import Mem0MemoryStore
from agent.repositories import AgentsRepository, ApprovalsRepository, JobsRepository
from agent.service import AgentService, ExecutionMode, ExecutionRequest
from agent.session_store import RedisSessionStore
from api.config import Settings, get_settings
from api.db import create_session_factory

logger = structlog.get_logger(__name__)


def _normalize_litellm_base_url(base_url: str) -> str:
    return base_url if base_url.rstrip("/").endswith("/v1") else f"{base_url.rstrip('/')}/v1"


async def run_agent_job_async(
    job_payload: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    jobs_repo: Any | None = None,
    agent_service: Any | None = None,
) -> dict[str, Any]:
    """Execute a queued agent job and persist its lifecycle to PostgreSQL."""
    runtime_settings = settings or get_settings()
    job_id = str(job_payload["job_id"])

    if jobs_repo is not None and agent_service is not None:
        return await _execute_job(job_payload, jobs_repo=jobs_repo, agent_service=agent_service)

    session_factory = create_session_factory(runtime_settings)
    async with session_factory() as session:
        jobs_repository = JobsRepository(session)

        redis_client = redis.from_url(runtime_settings.REDIS_URL)
        session_store = RedisSessionStore(
            redis_client=redis_client,
            session_ttl_seconds=runtime_settings.SESSION_TTL_SECONDS,
        )

        from agent import graphs as graph_factory
        from worker import queue as queue_factory

        service = AgentService(
            agent_repo=AgentsRepository(session),
            jobs_repo=jobs_repository,
            approvals_repo=ApprovalsRepository(session),
            session_store=session_store,
            memory_store=Mem0MemoryStore(runtime_settings),
            llm_client=LiteLLMClient(
                base_url=_normalize_litellm_base_url(runtime_settings.LITELLM_BASE_URL),
                api_key=runtime_settings.LITELLM_MASTER_KEY,
            ),
            settings=runtime_settings,
            graph_factory=graph_factory,
            queue_factory=queue_factory,
        )
        return await _execute_job(job_payload, jobs_repo=jobs_repository, agent_service=service)


def run_agent_job(
    job_payload: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    jobs_repo: Any | None = None,
    agent_service: Any | None = None,
):
    """rq-compatible entrypoint that also supports awaiting in unit tests."""
    coroutine = run_agent_job_async(
        job_payload,
        settings=settings,
        jobs_repo=jobs_repo,
        agent_service=agent_service,
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    return coroutine


async def _execute_job(
    job_payload: Mapping[str, Any],
    *,
    jobs_repo: Any,
    agent_service: Any,
) -> dict[str, Any]:
    job_id = str(job_payload["job_id"])
    tenant_id = str(job_payload["tenant_id"])
    agent_id = str(job_payload["agent_id"])
    session_id = job_payload.get("session_id")
    execution_mode = ExecutionMode.SESSION if session_id else ExecutionMode.SYNC

    try:
        await jobs_repo.mark_running(job_id, started_at=datetime.now(timezone.utc))

        result = await agent_service.execute(
            ExecutionRequest(
                tenant_id=tenant_id,
                agent_id=agent_id,
                input=str(job_payload["input"]),
                mode=execution_mode,
                session_id=str(session_id) if session_id else None,
                metadata={
                    **dict(job_payload.get("metadata") or {}),
                    "job_id": job_id,
                },
            )
        )

        if str(getattr(result, "status", "completed")) == "interrupted":
            pending_approval_id = getattr(result, "pending_approval_id", None)
            if pending_approval_id:
                await jobs_repo.mark_interrupted(
                    job_id,
                    pending_approval_id=pending_approval_id,
                    trace_id=result.trace_id,
                )
            logger.info(
                "agent_job_interrupted",
                job_id=job_id,
                tenant_id=tenant_id,
                agent_id=agent_id,
                pending_approval_id=pending_approval_id,
            )
            return {
                "job_id": job_id,
                "status": "interrupted",
                "pending_approval_id": pending_approval_id,
                "trace_id": result.trace_id,
            }

        completed_at = datetime.now(timezone.utc)
        await jobs_repo.mark_completed(
            job_id,
            output=result.output,
            trace_id=result.trace_id,
            completed_at=completed_at,
        )

        logger.info(
            "agent_job_completed",
            job_id=job_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            trace_id=result.trace_id,
        )

        return {
            "job_id": job_id,
            "status": "completed",
            "output": result.output,
            "trace_id": result.trace_id,
        }
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        await jobs_repo.mark_failed(
            job_id,
            error=str(exc),
            completed_at=completed_at,
        )
        logger.exception(
            "agent_job_failed",
            job_id=job_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            error=str(exc),
        )
        return {
            "job_id": job_id,
            "status": "failed",
            "error": str(exc),
        }
