from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.db import AgentDefinitionsRepository


class AgentNotFoundError(Exception):
    """Raised when an agent definition does not exist."""


class AgentsRepository:
    """Repository facade for agent-definition lookup used by runtime services."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = AgentDefinitionsRepository(session)

    async def get_by_id(self, agent_id: UUID | str) -> Mapping[str, Any]:
        normalized_agent_id = UUID(str(agent_id))
        record = await self._repo.get_by_id(normalized_agent_id)
        if not record:
            raise AgentNotFoundError(f"Agent not found: {normalized_agent_id}")
        return record
