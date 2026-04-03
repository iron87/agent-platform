from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from api.models.base import APIModel


class AgentSummary(APIModel):
    id: UUID
    name: str
    graph_type: Literal["conversational", "tool_agent", "batch_agent"]
    model_alias: Literal["default", "fast", "embedding"]
    version: int
    semantic_memory_enabled: bool
    tools: list[str] = Field(default_factory=list)
    hitl_tools: list[str] = Field(default_factory=list)


class AgentListResponse(APIModel):
    agents: list[AgentSummary]


class AgentCreateRequest(APIModel):
    name: str = Field(min_length=1, max_length=120)
    prompt_file: str | None = Field(default=None, min_length=1, max_length=512)
    prompt_text: str | None = Field(default=None, min_length=1, max_length=65535)
    model_alias: Literal["default", "fast", "embedding"] = "default"
    graph_type: Literal["conversational", "tool_agent", "batch_agent"] = "conversational"
    tools: list[str] = Field(default_factory=list)
    hitl_tools: list[str] = Field(default_factory=list)
    max_execution_seconds: int = Field(default=60, ge=1)
    semantic_memory_enabled: bool = False

    @field_validator("hitl_tools")
    @classmethod
    def validate_hitl_subset(cls, value: list[str], info):
        tools = set(info.data.get("tools") or [])
        invalid = [item for item in value if item not in tools]
        if invalid:
            raise ValueError(f"hitl_tools must be subset of tools; invalid: {invalid}")
        return value


class AgentCreateResponse(APIModel):
    agent: AgentSummary
