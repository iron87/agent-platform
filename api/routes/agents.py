from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
import redis.asyncio as redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agent.llm import LiteLLMClient
from agent.repositories import AgentNotFoundError, AgentsRepository, ApprovalsRepository, JobsRepository
from agent.service import AgentService, ExecutionMode, ExecutionRequest
from agent.session_store import RedisSessionStore
from api.config import Settings
from api.db import get_db_session
from api.deps import TenantContext, get_current_tenant
from api.models.agents import AgentCreateRequest, AgentCreateResponse, AgentListResponse, AgentSummary
from api.logging import bind_correlation_context, clear_correlation_context
from api.models.run import ReplayRequest, RunRequest, RunResponse

router = APIRouter(tags=["agents"])


@router.get("/agents", response_model=AgentListResponse, status_code=status.HTTP_200_OK)
async def list_agents(
	tenant: Annotated[TenantContext, Depends(get_current_tenant)],
	session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentListResponse:
	clear_correlation_context()
	bind_correlation_context(tenant_id=tenant.tenant_id)

	repo = AgentsRepository(session)
	try:
		records = await repo.list_all()
		items = [
			AgentSummary(
				id=UUID(str(record["id"])),
				name=str(record["name"]),
				graph_type=str(record["graph_type"]),
				model_alias=str(record["model_alias"]),
				version=int(record.get("version") or 1),
				semantic_memory_enabled=bool(record.get("semantic_memory_enabled")),
			)
			for record in records
		]
		return AgentListResponse(agents=items)
	finally:
		clear_correlation_context()


@router.post("/agents", response_model=AgentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
	payload: AgentCreateRequest,
	tenant: Annotated[TenantContext, Depends(get_current_tenant)],
	session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentCreateResponse:
	clear_correlation_context()
	bind_correlation_context(tenant_id=tenant.tenant_id, agent_name=payload.name)

	repo = AgentsRepository(session)
	try:
		record = await repo.create_conversational(
			name=payload.name,
			prompt_file=payload.prompt_file,
			model_alias=payload.model_alias,
			max_execution_seconds=payload.max_execution_seconds,
			semantic_memory_enabled=payload.semantic_memory_enabled,
		)
		return AgentCreateResponse(
			agent=AgentSummary(
				id=UUID(str(record["id"])),
				name=str(record["name"]),
				graph_type=str(record["graph_type"]),
				model_alias=str(record["model_alias"]),
				version=int(record.get("version") or 1),
				semantic_memory_enabled=bool(record.get("semantic_memory_enabled")),
			)
		)
	except IntegrityError as exc:
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail=f"Agent with name '{payload.name}' already exists.",
		) from exc
	except ValueError as exc:
		raise HTTPException(
			status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
			detail=str(exc),
		) from exc
	finally:
		clear_correlation_context()


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
		jobs_repo=JobsRepository(session),
		approvals_repo=ApprovalsRepository(session),
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
	clear_correlation_context()
	bind_correlation_context(
		tenant_id=tenant.tenant_id,
		agent_id=payload.agent_id,
		session_id=payload.session_id,
	)

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
			"approval_endpoint": tenant.approval_endpoint,
		},
	)

	try:
		result = await service.execute(execution_request)
		bind_correlation_context(trace_id=result.trace_id, job_id=result.job_id)
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
			status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
			detail=str(exc),
		) from exc
	except Exception as exc:
		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
			detail=f"Agent execution failed: {exc}",
		) from exc
	finally:
		clear_correlation_context()

	return RunResponse(
		job_id=UUID(result.job_id) if result.job_id else uuid4(),
		output=result.output,
		status=result.status,
		pending_approval_id=UUID(result.pending_approval_id) if result.pending_approval_id else None,
		trace_id=result.trace_id,
		session_id=result.session_id,
	)


@router.post("/run/replay", response_model=RunResponse, status_code=status.HTTP_200_OK)
async def replay_trace(
	payload: ReplayRequest,
	request: Request,
	tenant: Annotated[TenantContext, Depends(get_current_tenant)],
	session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RunResponse:
	clear_correlation_context()
	bind_correlation_context(
		tenant_id=tenant.tenant_id,
		agent_id=payload.agent_id,
		session_id=payload.session_id,
		replay_of_trace_id=payload.trace_id,
	)

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
		result = await service.replay_trace(
			execution_request,
			source_trace_id=payload.trace_id,
		)
		bind_correlation_context(trace_id=result.trace_id, job_id=result.job_id)
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
			status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
			detail=str(exc),
		) from exc
	except Exception as exc:
		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
			detail=f"Trace replay failed: {exc}",
		) from exc
	finally:
		clear_correlation_context()

	return RunResponse(
		job_id=UUID(result.job_id) if result.job_id else uuid4(),
		output=result.output,
		status=result.status,
		pending_approval_id=UUID(result.pending_approval_id) if result.pending_approval_id else None,
		trace_id=result.trace_id,
		session_id=result.session_id,
	)
