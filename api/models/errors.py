from __future__ import annotations

from typing import Any

from api.models.base import APIModel


class ErrorResponse(APIModel):
    error: str
    code: str
    detail: dict[str, Any] | None = None
