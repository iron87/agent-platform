from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from agent.service import ExecutionMode, ExecutionResult
from agent.repositories.agents import AgentsRepository
from api.deps import TenantContext
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
