from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog

from agent.repositories import ApprovalsRepository, JobsRepository
from api.config import Settings, get_settings
from api.db import create_session_factory

logger = structlog.get_logger(__name__)


async def sweep_approval_timeouts_once_async(
    *,
    settings: Settings | None = None,
    approvals_repo: Any | None = None,
    jobs_repo: Any | None = None,
) -> int:
    """Mark expired pending approvals as timed out and fail related jobs."""
    runtime_settings = settings or get_settings()

    if approvals_repo is not None and jobs_repo is not None:
        return await _sweep(approvals_repo, jobs_repo)

    session_factory = create_session_factory(runtime_settings)
    async with session_factory() as session:
        repository = approvals_repo or ApprovalsRepository(session)
        job_repository = jobs_repo or JobsRepository(session)
        return await _sweep(repository, job_repository)


def sweep_approval_timeouts_once(
    *,
    settings: Settings | None = None,
    approvals_repo: Any | None = None,
    jobs_repo: Any | None = None,
):
    coroutine = sweep_approval_timeouts_once_async(
        settings=settings,
        approvals_repo=approvals_repo,
        jobs_repo=jobs_repo,
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    return coroutine


async def _sweep(approvals_repo: Any, jobs_repo: Any) -> int:
    processed = 0
    for approval in await approvals_repo.list_timed_out_pending(now=datetime.now(timezone.utc)):
        updated = await approvals_repo.mark_timed_out(approval["id"])
        if updated is None:
            continue

        await jobs_repo.mark_failed(
            updated["job_id"],
            error="Approval timed out",
            completed_at=datetime.now(timezone.utc),
        )
        processed += 1

    if processed:
        logger.info("approval_timeout_sweep_completed", processed=processed)
    return processed


if __name__ == "__main__":
    sweep_approval_timeouts_once()
