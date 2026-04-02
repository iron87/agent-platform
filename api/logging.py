from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(log_level: str = "info") -> None:
    """Configure stdlib logging and structlog JSON rendering."""

    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processor=structlog.processors.JSONRenderer(),
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def get_logger(name: str):
    return structlog.get_logger(name)


def bind_correlation_context(**values: Any) -> None:
    """Bind correlation fields (e.g. trace_id) to structlog contextvars."""
    normalized: dict[str, Any] = {}
    for key, value in values.items():
        if value is None:
            continue
        normalized[key] = str(value)
    if normalized:
        structlog.contextvars.bind_contextvars(**normalized)


def clear_correlation_context() -> None:
    """Clear all bound structlog contextvars for the active request context."""
    structlog.contextvars.clear_contextvars()
