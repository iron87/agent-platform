from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, MetaData, String, Table, Text, func, insert, select, update
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import Uuid

from api.config import Settings, get_settings

metadata = MetaData()

tenants_table = Table(
    "tenants",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("name", Text, nullable=False),
    Column("api_key_hash", Text, nullable=False, unique=True),
    Column("approval_endpoint", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("is_active", Boolean, nullable=False, server_default="true"),
)

agent_definitions_table = Table(
    "agent_definitions",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("name", Text, nullable=False, unique=True),
    Column("model_alias", Text, nullable=False),
    Column("prompt_file", Text, nullable=False),
    Column("graph_type", Text, nullable=False),
    Column("tools", ARRAY(Text), nullable=False),
    Column("hitl_tools", ARRAY(Text), nullable=False),
    Column("max_execution_seconds", Integer, nullable=False),
    Column("semantic_memory_enabled", Boolean, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

jobs_table = Table(
    "jobs",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
    Column("agent_id", Uuid(as_uuid=True), ForeignKey("agent_definitions.id", ondelete="RESTRICT"), nullable=False),
    Column("session_id", Text),
    Column("input_payload", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("result", JSONB),
    Column("error", Text),
    Column("trace_id", Text),
    Column("rq_job_id", Text, unique=True),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("mode", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("started_at", DateTime(timezone=True)),
    Column("completed_at", DateTime(timezone=True)),
)

approval_requests_table = Table(
    "approval_requests",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("job_id", Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column("tenant_id", Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
    Column("tool_name", Text, nullable=False),
    Column("proposed_args", JSONB, nullable=False),
    Column("context_summary", Text),
    Column("status", Text, nullable=False),
    Column("timeout_at", DateTime(timezone=True), nullable=False),
    Column("decision_at", DateTime(timezone=True)),
    Column("reviewer_id", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

tenant_policies_table = Table(
    "tenant_policies",
    metadata,
    Column("tenant_id", Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("pii_rules_summary", JSONB),
    Column("blocked_categories", ARRAY(Text), nullable=False),
    Column("injection_detection_enabled", Boolean, nullable=False, server_default="false"),
    Column("colang_hash", Text),
    Column("last_loaded_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    runtime_settings = settings or get_settings()
    return create_async_engine(runtime_settings.DATABASE_URL, pool_pre_ping=True)


def create_session_factory(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    engine = create_engine(settings)
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope(
    settings: Settings | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> AsyncIterator[AsyncSession]:
    factory = session_factory or create_session_factory(settings)
    async with factory() as session:
        yield session


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


class Repository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def fetch_one(self, statement) -> Mapping[str, Any] | None:
        result = await self.session.execute(statement)
        row = result.mappings().first()
        return dict(row) if row is not None else None

    async def fetch_all(self, statement) -> list[Mapping[str, Any]]:
        result = await self.session.execute(statement)
        rows = result.mappings().all()
        return [dict(row) for row in rows]


class TenantsRepository(Repository):
    async def list_active_tenants(self) -> list[Mapping[str, Any]]:
        statement = select(tenants_table).where(tenants_table.c.is_active.is_(True))
        return await self.fetch_all(statement)

    async def get_by_id(self, tenant_id: UUID) -> Mapping[str, Any] | None:
        statement = select(tenants_table).where(tenants_table.c.id == tenant_id)
        return await self.fetch_one(statement)


class AgentDefinitionsRepository(Repository):
    async def get_by_id(self, agent_id: UUID) -> Mapping[str, Any] | None:
        statement = select(agent_definitions_table).where(agent_definitions_table.c.id == agent_id)
        return await self.fetch_one(statement)


class JobsRepository(Repository):
    async def get_by_id(self, job_id: UUID | str) -> Mapping[str, Any] | None:
        statement = select(jobs_table).where(jobs_table.c.id == UUID(str(job_id)))
        return await self.fetch_one(statement)

    async def create(self, values: Mapping[str, Any]) -> str:
        normalized_values = dict(values)
        for key in ("id", "tenant_id", "agent_id"):
            if key in normalized_values:
                normalized_values[key] = UUID(str(normalized_values[key]))

        statement = insert(jobs_table).values(**normalized_values).returning(jobs_table.c.id)
        result = await self.session.execute(statement)
        await self.session.commit()
        created_job_id = result.scalar_one()
        return str(created_job_id)

    async def update_rq_job_id(self, job_id: UUID | str, rq_job_id: str) -> None:
        statement = (
            update(jobs_table)
            .where(jobs_table.c.id == UUID(str(job_id)))
            .values(rq_job_id=rq_job_id)
        )
        await self.session.execute(statement)
        await self.session.commit()


class ApprovalRequestsRepository(Repository):
    async def get_by_id(self, approval_request_id: UUID) -> Mapping[str, Any] | None:
        statement = select(approval_requests_table).where(approval_requests_table.c.id == approval_request_id)
        return await self.fetch_one(statement)


class TenantPoliciesRepository(Repository):
    async def get_by_tenant_id(self, tenant_id: UUID) -> Mapping[str, Any] | None:
        statement = select(tenant_policies_table).where(tenant_policies_table.c.tenant_id == tenant_id)
        return await self.fetch_one(statement)
