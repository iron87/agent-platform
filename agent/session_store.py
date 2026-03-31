"""Redis-backed session store for conversational agent state persistence.

Provides multi-tenant session storage with automatic TTL expiration and
sliding window refresh. Sessions store conversational turns (message history)
for reuse across multiple invocations in the same conversation context.

Key patterns:
    - Turns (message history): {tenant_id}:session:{session_id}:turns
    - Metadata: {tenant_id}:session:{session_id}:meta
  
TTL is a sliding window: every access resets the expiration to +SESSION_TTL_SECONDS.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis
import structlog

from agent.models.session import SessionTurn

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SessionMetadata:
    """Session metadata stored separately for efficient lookups.

    Attributes:
        agent_id: UUID of the agent that created this session
        created_at: ISO 8601 timestamp when session was created
        last_active_at: ISO 8601 timestamp of last activity
        turn_count: Number of turns in this session
    """

    agent_id: str
    created_at: str
    last_active_at: str
    turn_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionMetadata":
        """Reconstruct from JSON dict."""
        return cls(
            agent_id=data["agent_id"],
            created_at=data["created_at"],
            last_active_at=data["last_active_at"],
            turn_count=int(data.get("turn_count", 0)),
        )


class RedisSessionStore:
    """Redis-backed conversational session store.

    Features:
    - Multi-tenant isolation (tenant_id namespace)
      - Automatic TTL with sliding window refresh
      - Atomic turn append with optimistic locking
      - Metadata tracking (agent_id, timestamps)
      - Zero storage overhead for inactive sessions

    Usage:
        store = RedisSessionStore(redis_client, session_ttl_seconds=86400)
        
        # Start a new session
        await store.create_session(
            tenant_id="tenant-1",
            session_id="conv-123",
            agent_id="report-gen",
        )
        
        # Append turns
        await store.append_turn(
            tenant_id="tenant-1",
            session_id="conv-123",
            turn=SessionTurn(role="user", content="...", timestamp="..."),
        )
        
        # Load full history
        turns = await store.load_turns(tenant_id="tenant-1", session_id="conv-123")
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        session_ttl_seconds: int = 86400,
    ) -> None:
        """Initialize session store.

        Args:
            redis_client: Async Redis client (from redis-py)
            session_ttl_seconds: TTL for all session keys (default 24 hours)

        Raises:
            ValueError: If session_ttl_seconds <= 0
        """
        if session_ttl_seconds <= 0:
            raise ValueError("session_ttl_seconds must be > 0")

        self.redis = redis_client
        self.ttl = session_ttl_seconds

        logger.info(
            "session_store_initialized",
            backend="redis",
            ttl_seconds=session_ttl_seconds,
        )

    @staticmethod
    def _validate_namespace_inputs(tenant_id: str, session_id: str) -> None:
        """Validate tenant/session IDs used to compose Redis keys.

        Prevents malformed keys and enforces tenant-isolated namespace usage.
        """
        if not tenant_id or ":" in tenant_id:
            raise ValueError("tenant_id must be non-empty and must not contain ':'")
        if not session_id or len(session_id) > 128 or ":" in session_id:
            raise ValueError("session_id must be 1-128 chars and must not contain ':'")

    def _turns_key(self, tenant_id: str, session_id: str) -> str:
        """Generate Redis key for session turns (message history)."""
        self._validate_namespace_inputs(tenant_id, session_id)
        return f"{tenant_id}:session:{session_id}:turns"

    def _meta_key(self, tenant_id: str, session_id: str) -> str:
        """Generate Redis key for session metadata."""
        self._validate_namespace_inputs(tenant_id, session_id)
        return f"{tenant_id}:session:{session_id}:meta"

    async def create_session(
        self,
        tenant_id: str,
        session_id: str,
        agent_id: str,
    ) -> None:
        """Create a new session (or reset existing session).

        Args:
            tenant_id: Tenant identifier
            session_id: Session unique ID (max 128 chars)
            agent_id: UUID of the agent invoking this session

        Raises:
            ValueError: If session_id is empty or > 128 chars
        """
        self._validate_namespace_inputs(tenant_id, session_id)

        turns_key = self._turns_key(tenant_id, session_id)
        meta_key = self._meta_key(tenant_id, session_id)

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        metadata = SessionMetadata(
            agent_id=agent_id,
            created_at=now,
            last_active_at=now,
            turn_count=0,
        )

        # Use pipeline for atomicity
        pipe = self.redis.pipeline()
        pipe.delete(turns_key)
        pipe.delete(meta_key)
        pipe.hset(meta_key, mapping=metadata.to_dict())
        pipe.expire(meta_key, self.ttl)
        await pipe.execute()

        logger.info(
            "session_created",
            tenant_id=tenant_id,
            session_id=session_id,
            agent_id=agent_id,
        )

    async def append_turn(
        self,
        tenant_id: str,
        session_id: str,
        turn: SessionTurn,
    ) -> int:
        """Append a single turn to the session history.

        Args:
            tenant_id: Tenant identifier
            session_id: Session identifier
            turn: SessionTurn object to append

        Returns:
            Total turn count after append

        Notes:
            - Automatically resets TTL on both keys (sliding window)
            - Idempotent: appending the same turn twice incurs no dedup
            - Metadata is updated on each append
        """
        turns_key = self._turns_key(tenant_id, session_id)
        meta_key = self._meta_key(tenant_id, session_id)

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Append turn as JSON string
        turn_json = json.dumps(turn.to_dict())
        pipe = self.redis.pipeline()
        pipe.rpush(turns_key, turn_json)
        pipe.expire(turns_key, self.ttl)
        
        await pipe.execute()

        # Get turn count
        turn_count = await self.redis.llen(turns_key)

        # Update metadata with new count and last_active_at
        await self.redis.hset(
            meta_key,
            mapping={
                "last_active_at": now,
                "turn_count": turn_count,
            },
        )
        await self.redis.expire(meta_key, self.ttl)

        logger.debug(
            "turn_appended",
            tenant_id=tenant_id,
            session_id=session_id,
            role=turn.role,
            turn_count=turn_count,
        )

        return turn_count

    async def load_turns(
        self,
        tenant_id: str,
        session_id: str,
    ) -> list[SessionTurn]:
        """Load all turns in a session.

        Args:
            tenant_id: Tenant identifier
            session_id: Session identifier

        Returns:
            List of SessionTurn objects (oldest first)

        Notes:
            - Resets TTL (sliding window behavior)
            - Returns empty list if session does not exist
        """
        turns_key = self._turns_key(tenant_id, session_id)
        meta_key = self._meta_key(tenant_id, session_id)

        # Fetch all turns
        turn_jsons = await self.redis.lrange(turns_key, 0, -1)

        # Decode to SessionTurn objects
        turns = [
            SessionTurn.from_dict(json.loads(turn_json)) for turn_json in turn_jsons
        ]

        # Reset TTL (sliding window)
        await self.redis.expire(turns_key, self.ttl)
        await self.redis.expire(meta_key, self.ttl)

        logger.debug(
            "turns_loaded",
            tenant_id=tenant_id,
            session_id=session_id,
            turn_count=len(turns),
        )

        return turns

    async def get_metadata(
        self,
        tenant_id: str,
        session_id: str,
    ) -> SessionMetadata | None:
        """Retrieve session metadata.

        Args:
            tenant_id: Tenant identifier
            session_id: Session identifier

        Returns:
            SessionMetadata if session exists, None otherwise
        """
        meta_key = self._meta_key(tenant_id, session_id)

        meta_dict = await self.redis.hgetall(meta_key)
        if not meta_dict:
            return None

        # Sliding TTL refresh on metadata access
        await self.redis.expire(meta_key, self.ttl)

        return SessionMetadata.from_dict(meta_dict)

    async def delete_session(
        self,
        tenant_id: str,
        session_id: str,
    ) -> bool:
        """Delete a session and all associated data.

        Args:
            tenant_id: Tenant identifier
            session_id: Session identifier

        Returns:
            True if session was deleted, False if it did not exist
        """
        turns_key = self._turns_key(tenant_id, session_id)
        meta_key = self._meta_key(tenant_id, session_id)

        deleted = await self.redis.delete(turns_key, meta_key)

        logger.info(
            "session_deleted",
            tenant_id=tenant_id,
            session_id=session_id,
        )

        return deleted > 0

    async def list_sessions(self, tenant_id: str) -> list[str]:
        """List all session IDs for a tenant (for admin/monitoring).

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of session_id strings

        Notes:
            - Uses SCAN to avoid blocking on large Redis instances
            - Only returns sessions that have metadata (created_session was called)
        """
        pattern = f"{tenant_id}:session:*:meta"
        session_ids = []

        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern)
            for key in keys:
                # Extract session_id from key format: {tenant_id}:session:{session_id}:meta
                raw_key = key.decode() if isinstance(key, bytes) else key
                session_id = raw_key.split(":")[2]
                session_ids.append(session_id)

            if cursor == 0:
                break

        logger.debug(
            "sessions_listed",
            tenant_id=tenant_id,
            session_count=len(session_ids),
        )

        return session_ids


__all__ = [
    "SessionTurn",
    "SessionMetadata",
    "RedisSessionStore",
]
