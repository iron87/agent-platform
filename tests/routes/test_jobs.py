from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from agent.service import ExecutionMode, ExecutionResult
from api.deps import TenantContext
from api.models.jobs import JobSubmitRequest
import api.routes.jobs as jobs_module


class _FakeAgentService:
    def __init__(self, result: ExecutionResult) -> None:
        self._result = result
        self.requests = []

    async def execute(self, request):
        self.requests.append(request)
        return self._result


def _build_request() -> SimpleNamespace:
    settings = SimpleNamespace()
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings)))


@pytest.mark.asyncio
async def test_submit_job_returns_pending_response(monkeypatch) -> None:
    tenant = TenantContext(tenant_id=uuid4(), tenant_name="acme", approval_endpoint=None)
    agent_id = uuid4()
    job_id = uuid4()
    payload = JobSubmitRequest(agent_id=agent_id, input="Generate a summary")
    fake_service = _FakeAgentService(
        ExecutionResult(
            output="",
            trace_id=None,
            job_id=str(job_id),
            execution_time_ms=0,
        )
    )

    monkeypatch.setattr(jobs_module, "_build_agent_service", lambda session, settings: fake_service)

    response = await jobs_module.submit_job(
        payload=payload,
        request=_build_request(),
        tenant=tenant,
        session=object(),
    )

    assert response.job_id == job_id
    assert response.status == "pending"
    assert len(fake_service.requests) == 1
    assert fake_service.requests[0].mode == ExecutionMode.ASYNC
    assert fake_service.requests[0].tenant_id == str(tenant.tenant_id)


@pytest.mark.asyncio
async def test_get_job_returns_completed_status_for_own_tenant(monkeypatch) -> None:
    tenant_id = uuid4()
    tenant = TenantContext(tenant_id=tenant_id, tenant_name="acme", approval_endpoint=None)
    job_id = uuid4()
    now = datetime.now(timezone.utc)

    class _FakeJobsRepository:
        async def get_by_id(self, requested_job_id):
            assert str(requested_job_id) == str(job_id)
            return {
                "id": job_id,
                "tenant_id": tenant_id,
                "status": "completed",
                "result": {"output": "done"},
                "error": None,
                "trace_id": "trace-123",
                "created_at": now,
                "started_at": now,
                "completed_at": now,
            }

    monkeypatch.setattr(jobs_module, "_build_jobs_repository", lambda session: _FakeJobsRepository())

    response = await jobs_module.get_job(
        job_id=job_id,
        tenant=tenant,
        session=object(),
    )

    assert response.job_id == job_id
    assert response.status == "completed"
    assert response.output == "done"
    assert response.trace_id == "trace-123"


@pytest.mark.asyncio
async def test_get_job_hides_other_tenant_records(monkeypatch) -> None:
    tenant = TenantContext(tenant_id=uuid4(), tenant_name="acme", approval_endpoint=None)
    job_id = uuid4()

    class _FakeJobsRepository:
        async def get_by_id(self, requested_job_id):
            assert str(requested_job_id) == str(job_id)
            return {
                "id": job_id,
                "tenant_id": uuid4(),
                "status": "completed",
                "result": {"output": "secret"},
                "error": None,
                "trace_id": None,
                "created_at": datetime.now(timezone.utc),
                "started_at": None,
                "completed_at": None,
            }

    monkeypatch.setattr(jobs_module, "_build_jobs_repository", lambda session: _FakeJobsRepository())

    with pytest.raises(HTTPException) as exc_info:
        await jobs_module.get_job(
            job_id=job_id,
            tenant=tenant,
            session=object(),
        )

    assert exc_info.value.status_code == 404
