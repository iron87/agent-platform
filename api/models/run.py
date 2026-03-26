from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from api.models.base import APIModel


class RunRequest(APIModel):
    agent_id: UUID
    input: str = Field(min_length=1, max_length=131072)
    session_id: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("session_id")
    @classmethod
    def normalize_session_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_id must not be blank.")
        return normalized


class RunResponse(APIModel):
    job_id: UUID
    output: str
    trace_id: str
    session_id: str | None = None
