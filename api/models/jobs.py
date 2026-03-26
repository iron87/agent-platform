from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from api.models.base import APIModel

JobState = Literal["pending", "running", "interrupted", "completed", "failed"]


class JobSubmitRequest(APIModel):
    agent_id: UUID
    input: str = Field(min_length=1, max_length=131072)
    session_id: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobSubmitResponse(APIModel):
    job_id: UUID
    status: Literal["pending"]


class JobStatus(APIModel):
    job_id: UUID
    status: JobState
    output: str | None = None
    error: str | None = None
    trace_id: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    pending_approval_id: UUID | None = None
