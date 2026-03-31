"""Per-tenant NeMo Guardrails policy registry with hot-reload support.

Provides:
- Per-tenant policy registry (one LLMRails instance per tenant)
- Automatic hot-reload via polling (20s interval, mtime/hash comparison)
- Zero-overhead pass-through for tenants without policies
- Atomic registry swaps to avoid data races
"""

import hashlib
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
import structlog

if TYPE_CHECKING:
    from nemoguardrails import LLMRails

logger = structlog.get_logger(__name__)

# Global policy registry with lock
_registry: dict[str, Any] = {}
_registry_lock = threading.Lock()
_config_hashes: dict[str, str] = {}
_last_refresh: float = 0.0


def _compute_dir_hash(directory: Path) -> str:
    """Compute hash of all files in a directory (for change detection).

    Args:
        directory: Path to directory (e.g., `agent/guardrails/{tenant_id}/`)

    Returns:
        SHA256 hex of sorted file contents (order-independent)
    """
    if not directory.is_dir():
        return ""

    hash_obj = hashlib.sha256()
    for file in sorted(directory.glob("*")):
        if file.is_file():
            hash_obj.update(file.read_bytes())

    return hash_obj.hexdigest()


def _build_rails(tenant_id: str, guardrails_dir: Path) -> Any | None:
    """Build LLMRails instance from Colang config directory.

    Args:
        tenant_id: Tenant identifier
        guardrails_dir: Base directory containing `{tenant_id}/` subdirs

    Returns:
        Initialized LLMRails instance, or None if config directory not found
    """
    from nemoguardrails import RailsConfig, LLMRails

    cfg_dir = guardrails_dir / tenant_id
    if not cfg_dir.is_dir():
        logger.debug("rails_config_dir_not_found", tenant_id=tenant_id, path=str(cfg_dir))
        return None

    try:
        config = RailsConfig.from_path(str(cfg_dir))
        rails = LLMRails(config)
        logger.info(
            "rails_config_loaded",
            tenant_id=tenant_id,
            config_dir=str(cfg_dir),
        )
        return rails
    except Exception as e:
        logger.error(
            "rails_config_load_failed",
            tenant_id=tenant_id,
            config_dir=str(cfg_dir),
            error=str(e),
        )
        return None


def initialize_policies(guardrails_dir: Path | str) -> None:
    """Initialize the policy registry (call once at startup).

    Loads all tenant policies from `guardrails_dir/{tenant_id}/` subdirectories.

    Args:
        guardrails_dir: Base directory containing per-tenant Colang configs
    """
    guardrails_dir = Path(guardrails_dir)

    if not guardrails_dir.is_dir():
        logger.warning(
            "guardrails_directory_not_found",
            path=str(guardrails_dir),
        )
        return

    with _registry_lock:
        _registry.clear()
        _config_hashes.clear()

        for cfg_dir in guardrails_dir.iterdir():
            if not cfg_dir.is_dir():
                continue

            tenant_id = cfg_dir.name
            rails = _build_rails(tenant_id, guardrails_dir)
            if rails:
                _registry[tenant_id] = rails
                _config_hashes[tenant_id] = _compute_dir_hash(cfg_dir)

    logger.info(
        "policies_initialized",
        guardrails_dir=str(guardrails_dir),
        tenant_count=len(_registry),
    )


def start_hot_reload_loop(
    guardrails_dir: Path | str,
    interval_seconds: int = 20,
) -> threading.Thread:
    """Start background thread to poll for policy config changes.

    Reloads policies if filenames or contents change. Updates are atomic
    (registry lock held during swap).

    Args:
        guardrails_dir: Base directory containing per-tenant configs
        interval_seconds: Polling interval (default 20s for ≤30s propagation)

    Returns:
        Thread object (daemon=True; exits when main thread exits)
    """
    guardrails_dir = Path(guardrails_dir)

    def _refresh_loop() -> None:
        while True:
            try:
                if not guardrails_dir.is_dir():
                    time.sleep(interval_seconds)
                    continue

                new_registry: dict[str, Any] = {}
                new_hashes: dict[str, str] = {}

                for cfg_dir in guardrails_dir.iterdir():
                    if not cfg_dir.is_dir():
                        continue

                    tenant_id = cfg_dir.name
                    dir_hash = _compute_dir_hash(cfg_dir)
                    old_hash = _config_hashes.get(tenant_id)

                    # Reload if hash changed
                    if old_hash != dir_hash:
                        rails = _build_rails(tenant_id, guardrails_dir)
                        if rails:
                            new_registry[tenant_id] = rails
                            new_hashes[tenant_id] = dir_hash
                            logger.info(
                                "policy_reloaded",
                                tenant_id=tenant_id,
                                old_hash=old_hash,
                                new_hash=dir_hash,
                            )
                    else:
                        # Hash unchanged; keep existing instance
                        with _registry_lock:
                            if tenant_id in _registry:
                                new_registry[tenant_id] = _registry[tenant_id]
                                new_hashes[tenant_id] = dir_hash

                # Atomic swap
                with _registry_lock:
                    _registry.clear()
                    _registry.update(new_registry)
                    _config_hashes.clear()
                    _config_hashes.update(new_hashes)

            except Exception as e:
                logger.error(
                    "policy_refresh_failed",
                    error_type=type(e).__name__,
                    error_message=str(e),
                )

            time.sleep(interval_seconds)

    thread = threading.Thread(target=_refresh_loop, daemon=True, name="policy-reload")
    thread.start()
    logger.info("policy_hot_reload_started", interval_seconds=interval_seconds)
    return thread


def get_rails(tenant_id: str) -> Any | None:
    """Retrieve LLMRails instance for a tenant.

    Returns None if no policy is configured (triggers pass-through behavior).

    Args:
        tenant_id: Tenant identifier

    Returns:
        LLMRails instance, or None for no-policy pass-through
    """
    with _registry_lock:
        return _registry.get(tenant_id)


async def apply_policy(
    rails: Any,
    prompt: str,
) -> tuple[str, dict[str, Any]]:
    """Apply a policy (pre-processing) to a user prompt.

    Args:
        rails: LLMRails instance
        prompt: User input text

    Returns:
        (processed_text, metadata) tuple
            - processed_text: Potentially sanitized/filtered input
            - metadata: Dict with 'violations', 'redactions', etc.
    """
    try:
        # LLMRails.generate() is the intended API, but we can also use
        # lower-level methods for pre-processing only
        result = rails.generate(prompt[:4096], context={})
        return result.get("body", prompt), {"status": "approved"}
    except Exception as e:
        logger.warning(
            "policy_application_failed",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        # Fail-open: return original prompt
        return prompt, {"status": "error", "error": str(e)}


__all__ = [
    "initialize_policies",
    "start_hot_reload_loop",
    "get_rails",
    "apply_policy",
]
