from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog

from agent.repositories import JobsRepository
from api.config import Settings, get_settings
from api.db import create_session_factory
from worker.queue import QueueUnavailableError, create_queue, get_job_status

logger = structlog.get_logger(__name__)


async def reconcile_jobs_once_async(
    *,
    settings: Settings | None = None,
    jobs_repo: Any | None = None,
    queue: Any | None = None,
) -> int:
    """Run one reconciliation pass between rq and PostgreSQL."""
    runtime_settings = settings or get_settings()

    if jobs_repo is not None and queue is not None:
        return await _reconcile(jobs_repo, queue)

    try:
        rq_queue = queue or create_queue(
            runtime_settings.REDIS_URL,
            queue_name=runtime_settings.RQ_QUEUE_NAME,
            job_timeout_seconds=runtime_settings.JOB_TIMEOUT_SECONDS,
        )
    except QueueUnavailableError as exc:
        logger.warning("job_reconcile_queue_unavailable", error=str(exc))
        return 0

    session_factory = create_session_factory(runtime_settings)
    async with session_factory() as session:
        repository = jobs_repo or JobsRepository(session)
        return await _reconcile(repository, rq_queue)


def reconcile_jobs_once(
    *,
    settings: Settings | None = None,
    jobs_repo: Any | None = None,
    queue: Any | None = None,
):
    """Run a reconciliation pass; works both from scripts and async tests."""
    coroutine = reconcile_jobs_once_async(settings=settings, jobs_repo=jobs_repo, queue=queue)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    return coroutine


async def reconcile_forever(
    *,
    settings: Settings | None = None,
    poll_interval_seconds: int = 30,
) -> None:
    runtime_settings = settings or get_settings()
    while True:
        updated = await reconcile_jobs_once_async(settings=runtime_settings)
        logger.debug("job_reconcile_pass_completed", updated=updated)
        await asyncio.sleep(poll_interval_seconds)


async def _reconcile(jobs_repo: Any, queue: Any) -> int:
    updated = 0
    for job in await jobs_repo.list_incomplete():
        rq_job_id = job.get("rq_job_id")
        if not rq_job_id:
            continue

        rq_status = get_job_status(queue, str(rq_job_id))
        if not rq_status:
            continue

        status = str(rq_status.get("status") or "").lower()
        job_id = str(job["id"])

        if status in {"started", "running"} and job.get("status") != "running":
            await jobs_repo.mark_running(
                job_id,
                started_at=rq_status.get("started_at") or datetime.now(timezone.utc),
            )
            updated += 1
            continue

        if status in {"finished", "completed"} and job.get("status") != "completed":
            result_payload = rq_status.get("result")
            if isinstance(result_payload, dict):
                output = str(result_payload.get("output") or "")
                trace_id = result_payload.get("trace_id")
            else:
                output = "" if result_payload is None else str(result_payload)
                trace_id = None
            await jobs_repo.mark_completed(
                job_id,
                output=output,
                trace_id=trace_id,
                completed_at=rq_status.get("ended_at") or datetime.now(timezone.utc),
            )
            updated += 1
            continue

        if status in {"failed", "stopped", "canceled", "cancelled"} and job.get("status") != "failed":
            await jobs_repo.mark_failed(
                job_id,
                error=str(rq_status.get("exc_info") or "Job failed in worker queue"),
                completed_at=rq_status.get("ended_at") or datetime.now(timezone.utc),
            )
            updated += 1

    return updated


def main() -> None:
    asyncio.run(reconcile_forever())


if __name__ == "__main__":
    main()
