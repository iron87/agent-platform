from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.db import ApprovalRequestsRepository as DBApprovalRequestsRepository


class ApprovalsRepository:
    """Repository facade for approval request lifecycle operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = DBApprovalRequestsRepository(session)

    async def get_for_tenant(self, approval_id: UUID | str, tenant_id: UUID | str) -> Mapping[str, Any] | None:
        return await self._repo.get_for_tenant(approval_id, tenant_id)

    async def create(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._repo.create(values)

    async def decide_pending(
        self,
        approval_id: UUID | str,
        *,
        approved: bool,
        reviewer_id: str,
    ) -> Mapping[str, Any] | None:
        return await self._repo.decide_pending(
            approval_id,
            approved=approved,
            reviewer_id=reviewer_id,
        )

    async def mark_timed_out(self, approval_id: UUID | str) -> Mapping[str, Any] | None:
        return await self._repo.mark_timed_out(approval_id)

    async def list_timed_out_pending(self, *, now: datetime | None = None) -> list[Mapping[str, Any]]:
        return await self._repo.list_timed_out_pending(now=now)
