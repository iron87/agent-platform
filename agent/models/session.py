"""Session models for conversational turn serialization."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SessionTurn:
    """A single conversational turn stored in Redis.

    Attributes:
        role: Message role, expected values are "user" or "assistant".
        content: Message text.
        timestamp: ISO 8601 UTC timestamp for the turn.
    """

    role: str
    content: str
    timestamp: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "SessionTurn":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data["timestamp"],
        )


__all__ = ["SessionTurn"]
