from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from agent.service import ExecutionMode, ExecutionResult
from worker.reconcile import reconcile_jobs_once
from worker.tasks import run_agent_job


class _FakeJobsRepository:
    def __init__(self) -> None:
        self.running: list[tuple[str, datetime | None]] = []
        self.completed: list[tuple[str, str, str | None, datetime | None]] = []
        self.failed: list[tuple[str, str, datetime | None]] = []
        self.open_jobs: list[dict[str, object]] = []

    async def mark_running(self, job_id: str, *, started_at: datetime | None = None) -> None:
        self.running.append((job_id, started_at))

    async def mark_completed(
        self,
        job_id: str,
        *,
        output: str,
        trace_id: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        self.completed.append((job_id, output, trace_id, completed_at))

    async def mark_failed(self, job_id: str, *, error: str, completed_at: datetime | None = None) -> None:
        self.failed.append((job_id, error, completed_at))

    async def list_incomplete(self) -> list[dict[str, object]]:
        return list(self.open_jobs)


class _FakeAgentService:
    def __init__(self, result: ExecutionResult) -> None:
        self.result = result
        self.requests = []

    async def execute(self, request):
        self.requests.append(request)
        return self.result


@pytest.mark.asyncio
async def test_run_agent_job_marks_job_completed() -> None:
    job_id = str(uuid4())
    jobs_repo = _FakeJobsRepository()
    agent_service = _FakeAgentService(
        ExecutionResult(
            output="async result",
            trace_id="trace-1",
            execution_time_ms=12,
        )
    )

    result = await run_agent_job(
        {
            "job_id": job_id,
            "tenant_id": str(uuid4()),
            "agent_id": str(uuid4()),
            "input": "Summarize the backlog",
            "metadata": {"source": "test"},
        },
        jobs_repo=jobs_repo,
        agent_service=agent_service,
    )

    assert result["status"] == "completed"
    assert jobs_repo.running and jobs_repo.running[0][0] == job_id
    assert jobs_repo.completed and jobs_repo.completed[0][0] == job_id
    assert jobs_repo.completed[0][1] == "async result"
    assert agent_service.requests[0].mode == ExecutionMode.SYNC


@pytest.mark.asyncio
async def test_reconcile_jobs_once_syncs_finished_rq_jobs() -> None:
    jobs_repo = _FakeJobsRepository()
    job_id = str(uuid4())
    jobs_repo.open_jobs = [
        {
            "id": job_id,
            "rq_job_id": "rq-1",
            "status": "running",
        }
    ]

    class _FakeRqJob:
        id = "rq-1"
        result = {"output": "done"}
        exc_info = None
        created_at = datetime.now(timezone.utc)
        started_at = datetime.now(timezone.utc)
        ended_at = datetime.now(timezone.utc)

        def get_status(self) -> str:
            return "finished"

    class _FakeQueue:
        def fetch_job(self, requested_job_id: str):
            assert requested_job_id == "rq-1"
            return _FakeRqJob()

    updated = await reconcile_jobs_once(jobs_repo=jobs_repo, queue=_FakeQueue())

    assert updated == 1
    assert jobs_repo.completed and jobs_repo.completed[0][0] == job_id
    assert jobs_repo.completed[0][1] == "done"
