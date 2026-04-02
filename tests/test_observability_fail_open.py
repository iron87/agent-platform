from __future__ import annotations

from types import SimpleNamespace

from agent.observability import create_langfuse_handler, fallback_trace_id


def test_create_langfuse_handler_returns_none_when_disabled() -> None:
    settings = SimpleNamespace(LANGFUSE_ENABLED=False)

    handler = create_langfuse_handler(settings)

    assert handler is None


def test_fallback_trace_id_is_deterministic() -> None:
    assert fallback_trace_id("job-123") == "local-job-123"
