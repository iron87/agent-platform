from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from api.models.base import APIModel


class ApprovalRequest(APIModel):
    id: UUID
    job_id: UUID
    tool_name: str
    proposed_args: dict[str, Any]
    context_summary: str | None = None
    status: str
    timeout_at: datetime
    decision_at: datetime | None = None
    created_at: datetime


class ApprovalDecision(APIModel):
    approved: bool
    reason: str | None = None
    reviewer_id: str = Field(min_length=1)
