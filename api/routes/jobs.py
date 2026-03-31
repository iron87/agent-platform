from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from agent.llm import LiteLLMClient
from agent.repositories import AgentNotFoundError, AgentsRepository, JobsRepository
from agent.service import AgentService, ExecutionMode, ExecutionRequest
from agent.session_store import RedisSessionStore
from api.config import Settings
from api.db import get_db_session
from api.deps import TenantContext, get_current_tenant
from api.models.jobs import JobStatus, JobSubmitRequest, JobSubmitResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _normalize_litellm_base_url(base_url: str) -> str:
    return base_url if base_url.rstrip("/").endswith("/v1") else f"{base_url.rstrip('/')}/v1"


def _build_agent_service(session: AsyncSession, settings: Settings) -> AgentService:
    from agent import graphs as graph_factory
    from worker import queue as queue_factory

    redis_client = redis.from_url(settings.REDIS_URL)
    session_store = RedisSessionStore(
        redis_client=redis_client,
        session_ttl_seconds=settings.SESSION_TTL_SECONDS,
    )

    return AgentService(
        agent_repo=AgentsRepository(session),
        jobs_repo=JobsRepository(session),
        session_store=session_store,
        memory_store=None,
        llm_client=LiteLLMClient(
            base_url=_normalize_litellm_base_url(settings.LITELLM_BASE_URL),
            api_key=settings.LITELLM_MASTER_KEY,
        ),
        settings=settings,
        graph_factory=graph_factory,
        queue_factory=queue_factory,
    )


def _build_jobs_repository(session: AsyncSession) -> JobsRepository:
    return JobsRepository(session)


def _extract_job_output(result: Any) -> str | None:
    if result is None:
        return None
    if isinstance(result, dict):
        output = result.get("output")
        return None if output is None else str(output)
    return str(result)


def _extract_pending_approval_id(result: Any) -> UUID | None:
    if not isinstance(result, dict):
        return None
    pending_approval_id = result.get("pending_approval_id")
    if not pending_approval_id:
        return None
    try:
        return UUID(str(pending_approval_id))
    except ValueError:
        return None


@router.post("", response_model=JobSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_job(
    payload: JobSubmitRequest,
    request: Request,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobSubmitResponse:
    settings: Settings = request.app.state.settings
    service = _build_agent_service(session, settings)

    execution_request = ExecutionRequest(
        tenant_id=str(tenant.tenant_id),
        agent_id=str(payload.agent_id),
        input=payload.input,
        mode=ExecutionMode.ASYNC,
        session_id=payload.session_id,
        metadata={
            **payload.metadata,
            "tenant_id": str(tenant.tenant_id),
        },
    )

    try:
        result = await service.execute(execution_request)
    except AgentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Job submission failed: {exc}",
        ) from exc

    if not result.job_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job submission did not return a job_id.",
        )

    return JobSubmitResponse(job_id=UUID(str(result.job_id)), status="pending")


@router.get("/{job_id}", response_model=JobStatus, status_code=status.HTTP_200_OK)
async def get_job(
    job_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobStatus:
    repo = _build_jobs_repository(session)
    record = await repo.get_by_id(job_id)

    if not record or str(record.get("tenant_id")) != str(tenant.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    result_payload = record.get("result")
    return JobStatus(
        job_id=UUID(str(record["id"])),
        status=str(record["status"]),
        output=_extract_job_output(result_payload),
        error=record.get("error"),
        trace_id=record.get("trace_id"),
        created_at=record["created_at"],
        started_at=record.get("started_at"),
        completed_at=record.get("completed_at"),
        pending_approval_id=_extract_pending_approval_id(result_payload),
    )
