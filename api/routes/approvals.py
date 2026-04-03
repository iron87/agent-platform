from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent.repositories import ApprovalsRepository, JobsRepository
from api.db import get_db_session
from api.deps import TenantContext, get_current_tenant
from api.models.approvals import ApprovalDecision, ApprovalRequest

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _to_approval_response(record: dict) -> ApprovalRequest:
	return ApprovalRequest(
		id=UUID(str(record["id"])),
		job_id=UUID(str(record["job_id"])),
		tool_name=str(record["tool_name"]),
		proposed_args=dict(record.get("proposed_args") or {}),
		context_summary=record.get("context_summary"),
		status=str(record["status"]),
		timeout_at=record["timeout_at"],
		decision_at=record.get("decision_at"),
		created_at=record["created_at"],
	)


@router.get("/{approval_id}", response_model=ApprovalRequest, status_code=status.HTTP_200_OK)
async def get_approval(
	approval_id: UUID,
	tenant: Annotated[TenantContext, Depends(get_current_tenant)],
	session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApprovalRequest:
	repo = ApprovalsRepository(session)
	record = await repo.get_for_tenant(approval_id, tenant.tenant_id)
	if record is None:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Approval request not found.",
		)
	return _to_approval_response(dict(record))


@router.post("/{approval_id}/decide", response_model=ApprovalRequest, status_code=status.HTTP_200_OK)
async def decide_approval(
	approval_id: UUID,
	payload: ApprovalDecision,
	tenant: Annotated[TenantContext, Depends(get_current_tenant)],
	session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApprovalRequest:
	approvals_repo = ApprovalsRepository(session)
	jobs_repo = JobsRepository(session)

	existing = await approvals_repo.get_for_tenant(approval_id, tenant.tenant_id)
	if existing is None:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Approval request not found.",
		)

	updated = await approvals_repo.decide_pending(
		approval_id,
		approved=payload.approved,
		reviewer_id=payload.reviewer_id,
	)
	if updated is None:
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail="Approval request is no longer pending.",
		)

	if payload.approved:
		await jobs_repo.mark_running(updated["job_id"])
	else:
		reason = payload.reason or "Approval rejected by reviewer"
		await jobs_repo.mark_failed(updated["job_id"], error=reason)

	return _to_approval_response(dict(updated))
