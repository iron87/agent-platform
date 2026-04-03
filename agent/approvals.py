from __future__ import annotations

from typing import Any, Mapping

import httpx
import structlog

logger = structlog.get_logger(__name__)


async def dispatch_approval_webhook(
    *,
    endpoint: str | None,
    approval: Mapping[str, Any],
    timeout_seconds: int = 5,
) -> bool:
    """Send approval payload to tenant callback endpoint (fail-open)."""
    if not endpoint:
        return False

    payload = {
        "event": "approval_requested",
        "approval_id": str(approval.get("id")),
        "job_id": str(approval.get("job_id")),
        "tool_name": approval.get("tool_name"),
        "status": approval.get("status"),
        "timeout_at": str(approval.get("timeout_at")),
        "context_summary": approval.get("context_summary"),
        "proposed_args": approval.get("proposed_args") or {},
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
        logger.info("approval_webhook_dispatched", endpoint=endpoint, approval_id=payload["approval_id"])
        return True
    except Exception as exc:  # pragma: no cover - network errors are environment-dependent
        logger.warning(
            "approval_webhook_dispatch_failed",
            endpoint=endpoint,
            approval_id=payload["approval_id"],
            error=str(exc),
        )
        return False
