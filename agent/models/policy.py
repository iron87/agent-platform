from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RedactionRule(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    pattern: str = Field(min_length=1, max_length=500)
    replacement: str = "[REDACTED]"


class TenantPolicyConfig(BaseModel):
    version: int = Field(default=1, ge=1)
    blocked_categories: list[str] = Field(default_factory=list)
    injection_detection_enabled: bool = False
    block_if_injection: bool = False
    redaction_rules: list[RedactionRule] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "TenantPolicyConfig":
        return cls.model_validate(value or {})


class PolicyResult(BaseModel):
    status: Literal["approved", "redacted", "blocked", "error", "pass_through"]
    violations: list[str] = Field(default_factory=list)
    redactions: list[str] = Field(default_factory=list)
    blocked_category: str | None = None
    injection_detected: bool = False
