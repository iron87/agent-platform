from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import TenantsRepository, get_db_session


@dataclass(frozen=True)
class TenantContext:
    tenant_id: UUID
    tenant_name: str
    approval_endpoint: str | None


async def get_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> str:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
        )
    return x_api_key


def _verify_api_key(provided_key: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(provided_key.encode("utf-8"), stored_hash.encode("utf-8"))
    except ValueError:
        return secrets.compare_digest(provided_key, stored_hash)


async def get_current_tenant(
    api_key: Annotated[str, Depends(get_api_key)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TenantContext:
    repository = TenantsRepository(session)
    candidates = await repository.list_active_tenants()

    for tenant in candidates:
        api_key_hash = str(tenant["api_key_hash"])
        if _verify_api_key(api_key, api_key_hash):
            return TenantContext(
                tenant_id=tenant["id"],
                tenant_name=str(tenant["name"]),
                approval_endpoint=tenant.get("approval_endpoint"),
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key.",
    )
