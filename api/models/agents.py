from __future__ import annotations

from typing import Literal
from uuid import UUID

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
