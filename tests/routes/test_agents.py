from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from agent.service import ExecutionMode, ExecutionResult
from agent.repositories.agents import AgentsRepository
from api.deps import TenantContext
from api.models.agents import AgentCreateRequest
from api.models.run import ReplayRequest, RunRequest
import api.routes.agents as agents_module


class _FakeAgentService:
    def __init__(self) -> None:
        self.executions = []
        self.replays = []

    async def execute(self, request):
        self.executions.append(request)
        return ExecutionResult(
            output="ok",
            trace_id="trace-sync-123",
            job_id=str(uuid4()),
            session_id=request.session_id,
            execution_time_ms=12,
        )

    async def replay_trace(self, request, *, source_trace_id: str):
        self.replays.append((request, source_trace_id))
        return ExecutionResult(
            output="replayed",
            trace_id="trace-replay-456",
            job_id=str(uuid4()),
            session_id=request.session_id,
            execution_time_ms=15,
        )


def _build_request() -> SimpleNamespace:
    settings = SimpleNamespace()
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings)))


@pytest.mark.asyncio
async def test_run_agent_returns_trace_id(monkeypatch) -> None:
    tenant = TenantContext(tenant_id=uuid4(), tenant_name="acme", approval_endpoint=None)
    payload = RunRequest(agent_id=uuid4(), input="Hello")
    fake_service = _FakeAgentService()

    monkeypatch.setattr(agents_module, "_build_agent_service", lambda session, settings: fake_service)

    response = await agents_module.run_agent(
        payload=payload,
        request=_build_request(),
        tenant=tenant,
        session=object(),
    )

    assert response.output == "ok"
    assert response.trace_id == "trace-sync-123"
    assert len(fake_service.executions) == 1
    assert fake_service.executions[0].mode == ExecutionMode.SYNC


@pytest.mark.asyncio
async def test_replay_trace_reuses_source_trace_id(monkeypatch) -> None:
    tenant = TenantContext(tenant_id=uuid4(), tenant_name="acme", approval_endpoint=None)
    payload = ReplayRequest(
        trace_id="trace-source-001",
        agent_id=uuid4(),
        input="Replay this",
    )
    fake_service = _FakeAgentService()

    monkeypatch.setattr(agents_module, "_build_agent_service", lambda session, settings: fake_service)

    response = await agents_module.replay_trace(
        payload=payload,
        request=_build_request(),
        tenant=tenant,
        session=object(),
    )

    assert response.output == "replayed"
    assert response.trace_id == "trace-replay-456"
    assert len(fake_service.replays) == 1
    replay_request, source_trace_id = fake_service.replays[0]
    assert source_trace_id == "trace-source-001"
    assert replay_request.mode == ExecutionMode.SYNC


@pytest.mark.asyncio
async def test_list_agents_returns_defined_agents(monkeypatch) -> None:
    tenant = TenantContext(tenant_id=uuid4(), tenant_name="acme", approval_endpoint=None)

    async def fake_list_all(self):
        return [
            {
                "id": uuid4(),
                "name": "support-triage",
                "graph_type": "conversational",
                "model_alias": "default",
                "version": 2,
                "semantic_memory_enabled": True,
            }
        ]

    monkeypatch.setattr(AgentsRepository, "list_all", fake_list_all)

    response = await agents_module.list_agents(
        tenant=tenant,
        session=object(),
    )

    assert len(response.agents) == 1
    assert response.agents[0].name == "support-triage"
    assert response.agents[0].graph_type == "conversational"


@pytest.mark.asyncio
async def test_create_agent_returns_created_record(monkeypatch) -> None:
    tenant = TenantContext(tenant_id=uuid4(), tenant_name="acme", approval_endpoint=None)
    created_id = uuid4()

    async def fake_create_conversational(self, **kwargs):
        assert kwargs["name"] == "support-chat-2"
        return {
            "id": created_id,
            "name": "support-chat-2",
            "graph_type": "conversational",
            "model_alias": "default",
            "version": 1,
            "semantic_memory_enabled": False,
        }

    monkeypatch.setattr(AgentsRepository, "create_conversational", fake_create_conversational)

    response = await agents_module.create_agent(
        payload=AgentCreateRequest(
            name="support-chat-2",
            prompt_file="examples/prompts/us2_support_prompt.txt",
        ),
        tenant=tenant,
        session=object(),
    )

    assert response.agent.id == created_id
    assert response.agent.name == "support-chat-2"
    assert response.agent.graph_type == "conversational"


@pytest.mark.asyncio
async def test_create_agent_maps_validation_error(monkeypatch) -> None:
    tenant = TenantContext(tenant_id=uuid4(), tenant_name="acme", approval_endpoint=None)

    async def fake_create_conversational(self, **kwargs):
        raise ValueError("invalid model alias")

    monkeypatch.setattr(AgentsRepository, "create_conversational", fake_create_conversational)

    with pytest.raises(HTTPException) as exc_info:
        await agents_module.create_agent(
            payload=AgentCreateRequest(
                name="bad-agent",
                prompt_file="examples/prompts/us2_support_prompt.txt",
            ),
            tenant=tenant,
            session=object(),
        )

    assert exc_info.value.status_code == 422
