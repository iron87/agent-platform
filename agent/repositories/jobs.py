from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import JobsRepository as DBJobsRepository
from api.db import jobs_table


class JobsRepository:
    """Repository facade for async-job lifecycle operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = DBJobsRepository(session)
        self._session = session

    async def get_by_id(self, job_id: UUID | str) -> Mapping[str, Any] | None:
        return await self._repo.get_by_id(job_id)

    async def get_by_rq_job_id(self, rq_job_id: str) -> Mapping[str, Any] | None:
        statement = select(jobs_table).where(jobs_table.c.rq_job_id == rq_job_id)
        return await self._repo.fetch_one(statement)

    async def create(self, values: Mapping[str, Any]) -> str:
        return await self._repo.create(values)

    async def update_rq_job_id(self, job_id: UUID | str, rq_job_id: str) -> None:
        await self._repo.update_rq_job_id(job_id, rq_job_id)

    async def mark_running(
        self,
        job_id: UUID | str,
        *,
        started_at: datetime | None = None,
    ) -> None:
        await self._update_job(
            job_id,
            status="running",
            started_at=started_at or datetime.now(timezone.utc),
            error=None,
            attempts=jobs_table.c.attempts + 1,
        )

    async def mark_completed(
        self,
        job_id: UUID | str,
        *,
        output: str | None = None,
        trace_id: str | None = None,
        completed_at: datetime | None = None,
        result: Mapping[str, Any] | None = None,
    ) -> None:
        result_payload = dict(result or {})
        if output is not None:
            result_payload.setdefault("output", output)

        await self._update_job(
            job_id,
            status="completed",
            result=result_payload or None,
            error=None,
            trace_id=trace_id,
            completed_at=completed_at or datetime.now(timezone.utc),
        )

    async def mark_failed(
        self,
        job_id: UUID | str,
        *,
        error: str,
        trace_id: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        await self._update_job(
            job_id,
            status="failed",
            error=error,
            trace_id=trace_id,
            completed_at=completed_at or datetime.now(timezone.utc),
        )

    async def mark_interrupted(
        self,
        job_id: UUID | str,
        *,
        pending_approval_id: UUID | str,
        trace_id: str | None = None,
    ) -> None:
        await self._update_job(
            job_id,
            status="interrupted",
            result={"pending_approval_id": str(pending_approval_id)},
            trace_id=trace_id,
        )

    async def list_incomplete(self) -> list[Mapping[str, Any]]:
        statement = select(jobs_table).where(jobs_table.c.status.in_(("pending", "running", "interrupted")))
        return await self._repo.fetch_all(statement)

    async def _update_job(self, job_id: UUID | str, **values: Any) -> None:
        statement = update(jobs_table).where(jobs_table.c.id == UUID(str(job_id))).values(**values)
        await self._session.execute(statement)
        await self._session.commit()
