from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.deps import TenantContext
from api.models.approvals import ApprovalDecision
import api.routes.approvals as approvals_module


@pytest.mark.asyncio
async def test_get_approval_returns_record(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant = TenantContext(tenant_id=uuid4(), tenant_name="acme", approval_endpoint=None)
    approval_id = uuid4()
    job_id = uuid4()

    async def fake_get_for_tenant(self, incoming_approval_id, incoming_tenant_id):
        assert str(incoming_approval_id) == str(approval_id)
        assert str(incoming_tenant_id) == str(tenant.tenant_id)
        return {
            "id": approval_id,
            "job_id": job_id,
            "tool_name": "rest_caller",
            "proposed_args": {"url": "https://example.com"},
            "context_summary": "High-risk outbound call",
            "status": "pending",
            "timeout_at": datetime.now(timezone.utc),
            "decision_at": None,
            "created_at": datetime.now(timezone.utc),
        }

    monkeypatch.setattr(approvals_module.ApprovalsRepository, "get_for_tenant", fake_get_for_tenant)

    response = await approvals_module.get_approval(
        approval_id=approval_id,
        tenant=tenant,
        session=object(),
    )

    assert response.id == approval_id
    assert response.job_id == job_id
    assert response.status == "pending"


@pytest.mark.asyncio
async def test_decide_approval_reject_marks_job_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant = TenantContext(tenant_id=uuid4(), tenant_name="acme", approval_endpoint=None)
    approval_id = uuid4()
    job_id = uuid4()

    async def fake_get_for_tenant(self, incoming_approval_id, incoming_tenant_id):
        return {
            "id": incoming_approval_id,
            "job_id": job_id,
            "tool_name": "rest_caller",
            "proposed_args": {},
            "context_summary": None,
            "status": "pending",
            "timeout_at": datetime.now(timezone.utc),
            "decision_at": None,
            "created_at": datetime.now(timezone.utc),
        }

    async def fake_decide_pending(self, incoming_approval_id, *, approved, reviewer_id):
        assert str(incoming_approval_id) == str(approval_id)
        assert approved is False
        assert reviewer_id == "reviewer-1"
        return {
            "id": approval_id,
            "job_id": job_id,
            "tool_name": "rest_caller",
            "proposed_args": {},
            "context_summary": None,
            "status": "rejected",
            "timeout_at": datetime.now(timezone.utc),
            "decision_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
        }

    called = {"mark_failed": 0}

    async def fake_mark_failed(self, incoming_job_id, *, error, trace_id=None, completed_at=None):
        assert str(incoming_job_id) == str(job_id)
        assert error == "No legal sign-off"
        called["mark_failed"] += 1

    monkeypatch.setattr(approvals_module.ApprovalsRepository, "get_for_tenant", fake_get_for_tenant)
    monkeypatch.setattr(approvals_module.ApprovalsRepository, "decide_pending", fake_decide_pending)
    monkeypatch.setattr(approvals_module.JobsRepository, "mark_failed", fake_mark_failed)

    response = await approvals_module.decide_approval(
        approval_id=approval_id,
        payload=ApprovalDecision(approved=False, reason="No legal sign-off", reviewer_id="reviewer-1"),
        tenant=tenant,
        session=object(),
    )

    assert response.status == "rejected"
    assert called["mark_failed"] == 1


@pytest.mark.asyncio
async def test_decide_approval_returns_conflict_if_not_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant = TenantContext(tenant_id=uuid4(), tenant_name="acme", approval_endpoint=None)
    approval_id = uuid4()

    async def fake_get_for_tenant(self, incoming_approval_id, incoming_tenant_id):
        return {
            "id": incoming_approval_id,
            "job_id": uuid4(),
            "tool_name": "rest_caller",
            "proposed_args": {},
            "context_summary": None,
            "status": "approved",
            "timeout_at": datetime.now(timezone.utc),
            "decision_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
        }

    async def fake_decide_pending(self, incoming_approval_id, *, approved, reviewer_id):
        return None

    monkeypatch.setattr(approvals_module.ApprovalsRepository, "get_for_tenant", fake_get_for_tenant)
    monkeypatch.setattr(approvals_module.ApprovalsRepository, "decide_pending", fake_decide_pending)

    with pytest.raises(HTTPException) as exc_info:
        await approvals_module.decide_approval(
            approval_id=approval_id,
            payload=ApprovalDecision(approved=True, reviewer_id="reviewer-2"),
            tenant=tenant,
            session=object(),
        )

    assert exc_info.value.status_code == 409
