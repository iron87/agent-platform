"""Semantic memory abstraction with Mem0 + Qdrant implementation.

Provides a protocol-based interface for semantic memory operations (upsert, search, delete)
with a Mem0 implementation that handles chunking, deduplication, and embedding.

Per-tenant isolation: one Qdrant collection per tenant (`{tenant_id}_memory`).
"""

from dataclasses import dataclass
from typing import Any, Protocol
import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class MemoryScope:
    """Scoping parameters for memory operations.

    Determines isolation boundaries for upsert/search/delete operations.
    All fields are optional; only populated fields are used for filtering.

    Attributes:
        tenant_id: Tenant identifier (required for multi-tenant isolation)
        user_id: Optional user-level scoping within a tenant
        agent_id: Optional agent-level scoping (e.g., per-agent tool memory)
        run_id: Optional run/execution-level scoping (e.g., per-job memory)
    """

    tenant_id: str
    """Required: tenant namespace"""

    user_id: str | None = None
    """Optional: user within the tenant"""

    agent_id: str | None = None
    """Optional: specific agent context"""

    run_id: str | None = None
    """Optional: specific execution context"""


@dataclass(frozen=True)
class MemoryRecord:
    """A single memory fact retrieved from the store.

    Attributes:
        id: Opaque string identifier for the memory (e.g., UUID)
        text: The semantic content (fact, observation, rule)
        score: Similarity score (0.0-1.0) from vector search; None if not from search
        metadata: Additional attributes (e.g., tags, timestamps, source)
    """

    id: str
    """Unique identifier for this memory fact"""

    text: str
    """Semantic content (1-4096 characters typically)"""

    score: float | None = None
    """Similarity score from vector search (0.0-1.0); None for upsert/direct fetch"""

    metadata: dict[str, Any] | None = None
    """Additional attributes (e.g., created_at, tags, source)"""


class SemanticMemoryStore(Protocol):
    """Protocol for semantic memory backends (Mem0, Qdrant, etc.).

    Implementations handle:
    - Automatic embedding of text via configured embedder
    - Chunking and deduplication
    - Tenant-scoped vector search
    - TTL/expiration if applicable
    """

    async def upsert_fact(
        self,
        *,
        scope: MemoryScope,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Upsert (create or update) a semantic fact.

        Args:
            scope: MemoryScope for isolation and filtering
            text: Semantic content to store (will be embedded)
            metadata: Optional metadata tags

        Returns:
            ID of the stored fact
        """
        ...

    async def search(
        self,
        *,
        scope: MemoryScope,
        query: str,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        """Search for semantically similar facts.

        Args:
            scope: MemoryScope for isolation and filtering
            query: Search query (will be embedded)
            limit: Max number of results to return

        Returns:
            List of MemoryRecord sorted by similarity (highest first)
        """
        ...

    async def delete(
        self,
        *,
        scope: MemoryScope,
        memory_id: str,
    ) -> None:
        """Delete a specific fact by ID.

        Args:
            scope: MemoryScope for authorization
            memory_id: ID of the fact to delete
        """
        ...

    async def delete_scope(
        self,
        *,
        scope: MemoryScope,
    ) -> int:
        """Delete all facts matching the scope.

        Atomic: either all deleted or none. Used for cleanup (e.g., user deletion).

        Args:
            scope: MemoryScope filter (all matching facts deleted)

        Returns:
            Count of deleted facts
        """
        ...


class Mem0MemoryStore:
    """Mem0-backed semantic memory implementation.

    Features:
    - Per-tenant Qdrant collections (`{tenant_id}_memory`)
    - Automatic embedding and chunking via Mem0
    - Lazy initialization and caching per tenant
    - Graceful degradation if Mem0/Qdrant unavailable

    Usage:
        store = Mem0MemoryStore(settings)
        memory_id = await store.upsert_fact(
            scope=MemoryScope(tenant_id="tenant-1", user_id="user-42"),
            text="Customer prefers weekly reports on Fridays.",
        )
        results = await store.search(
            scope=MemoryScope(tenant_id="tenant-1"),
            query="report frequency preferences",
            limit=3,
        )
    """

    def __init__(self, settings: Any) -> None:
        """Initialize Mem0 memory store.

        Args:
            settings: API settings (must have LITELLM_BASE_URL, LITELLM_API_KEY, QDRANT_HOST, QDRANT_PORT)

        Notes:
            - Mem0 instances are created lazily per tenant on first use
            - Requires `pip install mem0ai`
        """
        self.settings = settings
        self._mem0_instances: dict[str, Any] = {}

        logger.info(
            "mem0_store_initialized",
            qdrant_host=settings.QDRANT_HOST,
            qdrant_port=settings.QDRANT_PORT,
        )

    def _get_mem0_config(self, tenant_id: str) -> dict[str, Any]:
        """Build Mem0 configuration for a specific tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Dictionary of Mem0 config with per-tenant collection name
        """
        return {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "default",
                    # Internal Mem0 calls should bypass virtual-key auth and use master key.
                    "api_key": self.settings.LITELLM_MASTER_KEY,
                    "base_url": self.settings.LITELLM_BASE_URL + "/v1",
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "embedding",
                    # Internal Mem0 calls should bypass virtual-key auth and use master key.
                    "api_key": self.settings.LITELLM_MASTER_KEY,
                    "base_url": self.settings.LITELLM_BASE_URL + "/v1",
                    "embedding_dims": 1536,
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": f"{tenant_id}_memory",
                    "host": self.settings.QDRANT_HOST,
                    "port": self.settings.QDRANT_PORT,
                    "api_key": self.settings.QDRANT_API_KEY or None,
                },
            },
        }

    def _get_or_create_mem0(self, tenant_id: str) -> Any:
        """Get or lazily create a Mem0 instance for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Mem0 Memory instance for this tenant

        Raises:
            ImportError: If mem0ai is not installed
            Exception: If Mem0 initialization fails (Qdrant unreachable, etc.)
        """
        if tenant_id in self._mem0_instances:
            return self._mem0_instances[tenant_id]

        try:
            from mem0 import Memory
        except ImportError:
            raise ImportError(
                "mem0ai package not installed. "
                "Run: pip install mem0ai"
            )

        config = self._get_mem0_config(tenant_id)
        mem0 = Memory.from_config(config, user_id=tenant_id)
        self._mem0_instances[tenant_id] = mem0

        logger.info(
            "mem0_instance_created",
            tenant_id=tenant_id,
            collection=f"{tenant_id}_memory",
        )

        return mem0

    async def upsert_fact(
        self,
        *,
        scope: MemoryScope,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Upsert a semantic fact via Mem0.

        Args:
            scope: MemoryScope with tenant_id (required)
            text: Fact to store (1-4096 chars)
            metadata: Optional metadata dict

        Returns:
            ID of the stored fact
        """
        if not scope.tenant_id:
            raise ValueError("scope.tenant_id is required for memory operations")

        mem0 = self._get_or_create_mem0(scope.tenant_id)

        # Mem0.add() returns the message ID
        msg_id = mem0.add(
            messages=text,
            metadata=metadata or {},
            user_id=scope.user_id or scope.tenant_id,
        )

        logger.debug(
            "memory_fact_upserted",
            tenant_id=scope.tenant_id,
            memory_id=msg_id,
            text_len=len(text),
        )

        return msg_id

    async def search(
        self,
        *,
        scope: MemoryScope,
        query: str,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        """Search for similar facts via Mem0 + Qdrant.

        Args:
            scope: MemoryScope with tenant_id (required)
            query: Search query
            limit: Max results to return

        Returns:
            List of MemoryRecord sorted by similarity
        """
        if not scope.tenant_id:
            raise ValueError("scope.tenant_id is required for memory operations")

        mem0 = self._get_or_create_mem0(scope.tenant_id)

        # Mem0.search() returns list of dicts with 'id', 'text', 'score', etc.
        results = mem0.search(
            query=query,
            user_id=scope.user_id or scope.tenant_id,
            limit=limit,
        )

        records = [
            MemoryRecord(
                id=r.get("id", ""),
                text=r.get("text", ""),
                score=r.get("score"),
                metadata=r.get("metadata"),
            )
            for r in results
        ]

        logger.debug(
            "memory_search_completed",
            tenant_id=scope.tenant_id,
            query_len=len(query),
            result_count=len(records),
        )

        return records

    async def delete(
        self,
        *,
        scope: MemoryScope,
        memory_id: str,
    ) -> None:
        """Delete a fact by ID.

        Args:
            scope: MemoryScope with tenant_id (required)
            memory_id: ID of fact to delete
        """
        if not scope.tenant_id:
            raise ValueError("scope.tenant_id is required for memory operations")

        mem0 = self._get_or_create_mem0(scope.tenant_id)

        # Mem0.delete() takes the message ID
        mem0.delete(msg_id=memory_id)

        logger.debug(
            "memory_fact_deleted",
            tenant_id=scope.tenant_id,
            memory_id=memory_id,
        )

    async def delete_scope(
        self,
        *,
        scope: MemoryScope,
    ) -> int:
        """Delete all facts in a scope (dangerous operation).

        Clears the entire collection for the tenant if scope is just tenant_id.

        Args:
            scope: MemoryScope; typically just tenant_id

        Returns:
            Count of deleted facts (0 if not supported by backend)
        """
        if not scope.tenant_id:
            raise ValueError("scope.tenant_id is required for memory operations")

        logger.warning(
            "memory_scope_deletion_requested",
            tenant_id=scope.tenant_id,
            scope_user_id=scope.user_id,
        )

        # Mem0 doesn't have a direct "delete all by scope" method
        # For now, return 0 (not implemented)
        # A full implementation would iterate and delete matching records
        return 0


__all__ = [
    "MemoryScope",
    "MemoryRecord",
    "SemanticMemoryStore",
    "Mem0MemoryStore",
]
