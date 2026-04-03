from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from worker.approvals_timeout import sweep_approval_timeouts_once_async


class _FakeApprovalsRepo:
    def __init__(self) -> None:
        self.marked: list[str] = []
        self._approval_id = str(uuid4())
        self._job_id = str(uuid4())

    async def list_timed_out_pending(self, *, now=None):
        return [
            {
                "id": self._approval_id,
                "job_id": self._job_id,
                "status": "pending",
                "timeout_at": datetime.now(timezone.utc),
            }
        ]

    async def mark_timed_out(self, approval_id):
        self.marked.append(str(approval_id))
        return {
            "id": str(approval_id),
            "job_id": self._job_id,
            "status": "timed_out",
        }


class _FakeJobsRepo:
    def __init__(self) -> None:
        self.failed: list[str] = []

    async def mark_failed(self, job_id, *, error, trace_id=None, completed_at=None):
        assert error == "Approval timed out"
        self.failed.append(str(job_id))


@pytest.mark.asyncio
async def test_sweep_approval_timeouts_marks_approval_and_job() -> None:
    approvals_repo = _FakeApprovalsRepo()
    jobs_repo = _FakeJobsRepo()

    processed = await sweep_approval_timeouts_once_async(
        approvals_repo=approvals_repo,
        jobs_repo=jobs_repo,
    )

    assert processed == 1
    assert len(approvals_repo.marked) == 1
    assert len(jobs_repo.failed) == 1
