from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import api.deps as deps_module
from api.models.approvals import ApprovalDecision
from api.models.run import RunRequest


@pytest.mark.asyncio
async def test_get_api_key_missing_header_raises_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await deps_module.get_api_key(None)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_tenant_invalid_key_raises_401(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_list_active_tenants(self):
        return [
            {
                "id": uuid4(),
                "name": "acme",
                "api_key_hash": "different-key",
                "approval_endpoint": None,
            }
        ]

    monkeypatch.setattr(deps_module.TenantsRepository, "list_active_tenants", fake_list_active_tenants)

    with pytest.raises(HTTPException) as exc_info:
        await deps_module.get_current_tenant(api_key="provided-key", session=object())

    assert exc_info.value.status_code == 401


def test_run_request_rejects_reserved_metadata_keys() -> None:
    with pytest.raises(ValidationError):
        RunRequest(
            agent_id=uuid4(),
            input="hello",
            metadata={"tenant_id": "abc"},
        )


def test_approval_decision_requires_reviewer_id() -> None:
    with pytest.raises(ValidationError):
        ApprovalDecision(approved=True, reviewer_id="")
