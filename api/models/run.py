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
        if ":" in normalized:
            raise ValueError("session_id must not contain ':'.")
        return normalized

    @field_validator("metadata")
    @classmethod
    def validate_metadata_guards(cls, value: dict[str, Any]) -> dict[str, Any]:
        lowered = {k.lower() for k in value.keys()}
        forbidden = {"tenant_id", "client_id"}
        if lowered.intersection(forbidden):
            raise ValueError("metadata must not include tenant_id or client_id.")
        return value


class RunResponse(APIModel):
    job_id: UUID
    output: str
    trace_id: str | None = None
    session_id: str | None = None


class ReplayRequest(APIModel):
    trace_id: str = Field(min_length=1)
    agent_id: UUID
    input: str = Field(min_length=1, max_length=131072)
    session_id: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("session_id")
    @classmethod
    def normalize_replay_session_id(cls, value: str | None) -> str | None:
        return RunRequest.normalize_session_id(value)
