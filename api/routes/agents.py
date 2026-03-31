from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from agent.llm import LiteLLMClient
from agent.repositories import AgentNotFoundError, AgentsRepository
from agent.service import AgentService, ExecutionMode, ExecutionRequest
from agent.session_store import RedisSessionStore
from api.config import Settings
from api.db import get_db_session
from api.deps import TenantContext, get_current_tenant
from api.models.run import RunRequest, RunResponse

router = APIRouter(tags=["agents"])


def _normalize_litellm_base_url(base_url: str) -> str:
	return base_url if base_url.rstrip("/").endswith("/v1") else f"{base_url.rstrip('/')}/v1"


def _build_agent_service(session: AsyncSession, settings: Settings) -> AgentService:
	from agent import graphs as graph_factory

	redis_client = redis.from_url(settings.REDIS_URL)
	session_store = RedisSessionStore(
		redis_client=redis_client,
		session_ttl_seconds=settings.SESSION_TTL_SECONDS,
	)

	return AgentService(
		agent_repo=AgentsRepository(session),
		jobs_repo=None,
		session_store=session_store,
		memory_store=None,
		llm_client=LiteLLMClient(
			base_url=_normalize_litellm_base_url(settings.LITELLM_BASE_URL),
			# Internal service-to-service calls must use LiteLLM master key.
			# Tenant keys are validated through LiteLLM key management and can require DB connectivity.
			api_key=settings.LITELLM_MASTER_KEY,
		),
		settings=settings,
		graph_factory=graph_factory,
	)


@router.post("/run", response_model=RunResponse, status_code=status.HTTP_200_OK)
async def run_agent(
	payload: RunRequest,
	request: Request,
	tenant: Annotated[TenantContext, Depends(get_current_tenant)],
	session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RunResponse:
	settings: Settings = request.app.state.settings
	service = _build_agent_service(session, settings)

	execution_request = ExecutionRequest(
		tenant_id=str(tenant.tenant_id),
		agent_id=str(payload.agent_id),
		input=payload.input,
		mode=ExecutionMode.SESSION if payload.session_id else ExecutionMode.SYNC,
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
			detail=f"Agent execution failed: {exc}",
		) from exc

	return RunResponse(
		job_id=UUID(result.job_id) if result.job_id else uuid4(),
		output=result.output,
		trace_id=result.trace_id,
		session_id=result.session_id,
	)
