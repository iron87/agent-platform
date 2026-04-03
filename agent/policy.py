"""Per-tenant policy registry and enforcement pipeline with hot-reload support.

Provides:
- Per-tenant registry with optional NeMo guardrails instance and policy config
- Automatic hot-reload via polling + content hash detection
- Input/output policy evaluation with redaction and category blocking
- Optional prompt injection detection
- Fail-open behavior on runtime errors
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from agent.models.policy import PolicyResult, TenantPolicyConfig

logger = structlog.get_logger(__name__)

# Global policy registry with lock
_registry: dict[str, Any] = {}
_registry_lock = threading.Lock()
_config_hashes: dict[str, str] = {}
_policy_versions: dict[str, int] = {}
_last_refresh: float = 0.0

_POLICY_FILE_NAME = "policy.json"
_DEFAULT_BLOCK_MESSAGE = "Response blocked by tenant policy."

_CATEGORY_PATTERNS: dict[str, tuple[str, ...]] = {
    "pii": (r"\b\d{3}-\d{2}-\d{4}\b", r"\b\d{10,16}\b"),
    "credentials": (r"(?i)api[_-]?key", r"(?i)password", r"(?i)secret"),
    "violence": (r"(?i)kill", r"(?i)bomb", r"(?i)weapon"),
    "hate": (r"(?i)hate", r"(?i)racist", r"(?i)ethnic cleansing"),
}

_INJECTION_PATTERNS: tuple[str, ...] = (
    r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"(?i)reveal\s+(the\s+)?(system|hidden)\s+prompt",
    r"(?i)developer\s+mode",
    r"(?i)jailbreak",
    r"(?i)you\s+are\s+now",
)


@dataclass(frozen=True)
class PolicyBundle:
    tenant_id: str
    config: TenantPolicyConfig
    rails: Any | None = None


def _compute_dir_hash(directory: Path) -> str:
    """Compute hash of all files in a directory (for change detection)."""
    if not directory.is_dir():
        return ""

    hash_obj = hashlib.sha256()
    for file in sorted(directory.glob("*")):
        if file.is_file():
            hash_obj.update(file.read_bytes())

    return hash_obj.hexdigest()


def _load_policy_config(cfg_dir: Path) -> TenantPolicyConfig:
    policy_file = cfg_dir / _POLICY_FILE_NAME
    if not policy_file.exists():
        return TenantPolicyConfig()

    try:
        return TenantPolicyConfig.from_dict(json.loads(policy_file.read_text(encoding="utf-8")))
    except Exception as exc:
        logger.error(
            "policy_config_parse_failed",
            tenant_id=cfg_dir.name,
            file=str(policy_file),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return TenantPolicyConfig()


def _build_rails(tenant_id: str, guardrails_dir: Path) -> Any | None:
    """Build optional LLMRails instance from tenant config directory."""
    cfg_dir = guardrails_dir / tenant_id
    if not cfg_dir.is_dir():
        return None

    try:
        module = importlib.import_module("nemoguardrails")
        RailsConfig = getattr(module, "RailsConfig")
        LLMRails = getattr(module, "LLMRails")

        config = RailsConfig.from_path(str(cfg_dir))
        return LLMRails(config)
    except Exception as exc:
        logger.warning(
            "rails_load_failed_fail_open",
            tenant_id=tenant_id,
            config_dir=str(cfg_dir),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return None


def _build_policy_bundle(tenant_id: str, guardrails_dir: Path) -> PolicyBundle | None:
    cfg_dir = guardrails_dir / tenant_id
    if not cfg_dir.is_dir():
        return None

    config = _load_policy_config(cfg_dir)
    rails = _build_rails(tenant_id, guardrails_dir)
    return PolicyBundle(tenant_id=tenant_id, config=config, rails=rails)


def initialize_policies(guardrails_dir: Path | str) -> None:
    """Initialize policy registry from guardrails directory."""
    guardrails_dir = Path(guardrails_dir)

    if not guardrails_dir.is_dir():
        logger.warning("guardrails_directory_not_found", path=str(guardrails_dir))
        return

    with _registry_lock:
        _registry.clear()
        _config_hashes.clear()
        _policy_versions.clear()

        for cfg_dir in guardrails_dir.iterdir():
            if not cfg_dir.is_dir():
                continue

            tenant_id = cfg_dir.name
            bundle = _build_policy_bundle(tenant_id, guardrails_dir)
            if bundle is None:
                continue

            _registry[tenant_id] = bundle
            _config_hashes[tenant_id] = _compute_dir_hash(cfg_dir)
            _policy_versions[tenant_id] = bundle.config.version

    logger.info("policies_initialized", guardrails_dir=str(guardrails_dir), tenant_count=len(_registry))


def start_hot_reload_loop(
    guardrails_dir: Path | str,
    interval_seconds: int = 20,
) -> threading.Thread:
    """Start background thread to poll for policy config changes."""
    guardrails_dir = Path(guardrails_dir)

    def _refresh_loop() -> None:
        global _last_refresh

        while True:
            try:
                if not guardrails_dir.is_dir():
                    time.sleep(interval_seconds)
                    continue

                new_registry: dict[str, Any] = {}
                new_hashes: dict[str, str] = {}
                new_versions: dict[str, int] = {}

                for cfg_dir in guardrails_dir.iterdir():
                    if not cfg_dir.is_dir():
                        continue

                    tenant_id = cfg_dir.name
                    dir_hash = _compute_dir_hash(cfg_dir)
                    old_hash = _config_hashes.get(tenant_id)

                    if old_hash != dir_hash:
                        bundle = _build_policy_bundle(tenant_id, guardrails_dir)
                        if bundle is not None:
                            previous_version = _policy_versions.get(tenant_id, 0)
                            version = max(bundle.config.version, previous_version + 1)
                            updated_bundle = PolicyBundle(
                                tenant_id=tenant_id,
                                config=bundle.config.model_copy(update={"version": version}),
                                rails=bundle.rails,
                            )
                            new_registry[tenant_id] = updated_bundle
                            new_hashes[tenant_id] = dir_hash
                            new_versions[tenant_id] = version
                            logger.info(
                                "policy_reloaded",
                                tenant_id=tenant_id,
                                old_hash=old_hash,
                                new_hash=dir_hash,
                                policy_version=version,
                            )
                    else:
                        with _registry_lock:
                            existing = _registry.get(tenant_id)
                        if existing is not None:
                            new_registry[tenant_id] = existing
                            new_hashes[tenant_id] = dir_hash
                            new_versions[tenant_id] = _policy_versions.get(tenant_id, 1)

                with _registry_lock:
                    _registry.clear()
                    _registry.update(new_registry)
                    _config_hashes.clear()
                    _config_hashes.update(new_hashes)
                    _policy_versions.clear()
                    _policy_versions.update(new_versions)
                    _last_refresh = time.time()

            except Exception as exc:
                logger.error(
                    "policy_refresh_failed",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )

            time.sleep(interval_seconds)

    thread = threading.Thread(target=_refresh_loop, daemon=True, name="policy-reload")
    thread.start()
    logger.info("policy_hot_reload_started", interval_seconds=interval_seconds)
    return thread


def get_rails(tenant_id: str) -> Any | None:
    """Retrieve policy bundle for a tenant; None means pass-through."""
    with _registry_lock:
        return _registry.get(tenant_id)


def get_policy_version(tenant_id: str) -> int | None:
    with _registry_lock:
        return _policy_versions.get(tenant_id)


def _detect_blocked_category(text: str, blocked_categories: list[str]) -> str | None:
    lowered = text.lower()
    for category in blocked_categories:
        patterns = _CATEGORY_PATTERNS.get(category, ())
        for pattern in patterns:
            if re.search(pattern, lowered):
                return category
    return None


def _detect_prompt_injection(text: str) -> bool:
    return any(re.search(pattern, text) for pattern in _INJECTION_PATTERNS)


def _apply_redactions(text: str, config: TenantPolicyConfig) -> tuple[str, list[str], list[str]]:
    redacted_text = text
    redaction_hits: list[str] = []
    violation_labels: list[str] = []

    for rule in config.redaction_rules:
        try:
            redacted_text, count = re.subn(rule.pattern, rule.replacement, redacted_text)
            if count > 0:
                redaction_hits.append(rule.name)
                violation_labels.append(f"redaction:{rule.name}")
        except re.error:
            logger.warning("policy_redaction_rule_invalid", rule_name=rule.name)

    return redacted_text, redaction_hits, violation_labels


async def apply_policy(
    rails: Any,
    prompt: str,
    *,
    tenant_id: str | None = None,
    stage: str = "output",
) -> tuple[str, dict[str, Any]]:
    """Apply policy checks to text with fail-open behavior.

    Rules are driven by tenant `policy.json` when available. If unavailable,
    behavior is pass-through to keep zero-overhead no-policy path.
    """
    if rails is None:
        result = PolicyResult(status="pass_through")
        return prompt, result.model_dump()

    try:
        if isinstance(rails, PolicyBundle):
            config = rails.config
        else:
            # Backward compatibility if callers pass bare rails object.
            config = TenantPolicyConfig()

        blocked_category = _detect_blocked_category(prompt, config.blocked_categories)
        injection_detected = config.injection_detection_enabled and _detect_prompt_injection(prompt)
        redacted_text, redactions, violations = _apply_redactions(prompt, config)

        if injection_detected:
            violations.append("prompt_injection_detected")

        if blocked_category is not None:
            violations.append(f"blocked_category:{blocked_category}")

        should_block = blocked_category is not None or (injection_detected and config.block_if_injection)
        if should_block:
            logger.warning(
                "policy_violation_blocked",
                tenant_id=tenant_id,
                stage=stage,
                blocked_category=blocked_category,
                injection_detected=injection_detected,
                violation_count=len(violations),
            )
            result = PolicyResult(
                status="blocked",
                violations=violations,
                redactions=redactions,
                blocked_category=blocked_category,
                injection_detected=injection_detected,
            )
            return _DEFAULT_BLOCK_MESSAGE, result.model_dump()

        status = "redacted" if redactions else "approved"
        if violations:
            logger.info(
                "policy_violation_logged",
                tenant_id=tenant_id,
                stage=stage,
                violation_count=len(violations),
                redaction_count=len(redactions),
                injection_detected=injection_detected,
            )

        result = PolicyResult(
            status=status,
            violations=violations,
            redactions=redactions,
            injection_detected=injection_detected,
        )
        return redacted_text, result.model_dump()
    except Exception as exc:
        logger.warning(
            "policy_application_failed",
            tenant_id=tenant_id,
            stage=stage,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        # Fail-open behavior: return original text untouched.
        result = PolicyResult(status="error", violations=["policy_runtime_error"])
        return prompt, result.model_dump()


__all__ = [
    "initialize_policies",
    "start_hot_reload_loop",
    "get_rails",
    "get_policy_version",
    "apply_policy",
]
