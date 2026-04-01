from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agent.llm import VALID_ALIASES
from api.db import AgentDefinitionsRepository


class AgentNotFoundError(Exception):
    """Raised when an agent definition does not exist."""


class InvalidAgentDefinitionError(ValueError):
    """Raised when an agent definition contains unsupported runtime settings."""


class AgentsRepository:
    """Repository facade for agent-definition lookup used by runtime services."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = AgentDefinitionsRepository(session)

    async def get_by_id(self, agent_id: UUID | str) -> Mapping[str, Any]:
        normalized_agent_id = UUID(str(agent_id))
        record = await self._repo.get_by_id(normalized_agent_id)
        if not record:
            raise AgentNotFoundError(f"Agent not found: {normalized_agent_id}")

        validated_record = dict(record)
        model_alias = str(validated_record.get("model_alias") or "").strip()
        if model_alias not in VALID_ALIASES:
            raise InvalidAgentDefinitionError(
                f"Agent {normalized_agent_id} has invalid model_alias='{model_alias}'. "
                f"Expected one of {sorted(VALID_ALIASES)}."
            )

        validated_record["model_alias"] = model_alias
        return validated_record
