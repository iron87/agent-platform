from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from api.models.base import APIModel


class AgentSummary(APIModel):
    id: UUID
    name: str
    graph_type: Literal["conversational", "tool_agent", "batch_agent"]
    model_alias: Literal["default", "fast", "embedding"]
    version: int
    semantic_memory_enabled: bool


class AgentListResponse(APIModel):
    agents: list[AgentSummary]


class AgentCreateRequest(APIModel):
    name: str = Field(min_length=1, max_length=120)
    prompt_file: str = Field(min_length=1, max_length=512)
    model_alias: Literal["default", "fast", "embedding"] = "default"
    max_execution_seconds: int = Field(default=60, ge=1)
    semantic_memory_enabled: bool = False


class AgentCreateResponse(APIModel):
    agent: AgentSummary
