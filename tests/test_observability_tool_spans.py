"""Unit tests for tool-call span emission in observability callbacks."""

from __future__ import annotations

from agent.observability import emit_tool_call_span


class RecordingCallback:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def on_custom_event(self, *, name: str, data: dict) -> None:
        self.events.append((name, data))


class BrokenCallback:
    def on_custom_event(self, *, name: str, data: dict) -> None:
        raise RuntimeError("callback sink unavailable")



def test_emit_tool_call_span_success_event() -> None:
    cb = RecordingCallback()

    emit_tool_call_span(
        [cb],
        tool_name="code_exec",
        args={"code": "print(1)"},
        output={"stdout": "1\n", "exit_code": 0},
        error=None,
        attempt=1,
    )

    assert len(cb.events) == 1
    name, payload = cb.events[0]
    assert name == "tool_call"
    assert payload["tool_name"] == "code_exec"
    assert payload["attempt"] == 1
    assert payload["ok"] is True
    assert payload["error"] is None
    assert isinstance(payload["args"], str)



def test_emit_tool_call_span_error_event() -> None:
    cb = RecordingCallback()

    emit_tool_call_span(
        [cb],
        tool_name="rest_caller",
        args={"url": "http://example.com"},
        output=None,
        error="timeout",
        attempt=2,
    )

    name, payload = cb.events[0]
    assert name == "tool_call"
    assert payload["ok"] is False
    assert payload["error"] == "timeout"
    assert payload["attempt"] == 2



def test_emit_tool_call_span_is_fail_open() -> None:
    cb = RecordingCallback()

    emit_tool_call_span(
        [BrokenCallback(), cb],
        tool_name="file_ops",
        args={"action": "read_file", "path": "a.txt"},
        output={"content": "hello"},
        error=None,
        attempt=1,
    )

    # The broken callback must not stop the healthy callback.
    assert len(cb.events) == 1
