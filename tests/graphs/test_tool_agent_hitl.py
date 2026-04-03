from __future__ import annotations

import pytest

from agent.graphs.tool_agent import _tool_agent_step


class _FakeTool:
    name = "rest_caller"
    description = "Call an HTTP endpoint"
    input_schema = {"type": "object", "properties": {}}

    async def arun(self, **kwargs):  # pragma: no cover - should not be called in this test
        raise AssertionError("Tool should not run before approval")


class _FakeChoice:
    def __init__(self) -> None:
        self.finish_reason = "tool_calls"
        self.message = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "rest_caller",
                        "arguments": '{"url":"https://example.com"}',
                    },
                }
            ],
        }


class _FakeCompletion:
    def __init__(self) -> None:
        self.choices = [_FakeChoice()]


class _FakeLLM:
    async def create_completion(self, **kwargs):
        return _FakeCompletion()


@pytest.mark.asyncio
async def test_tool_agent_interrupts_when_tool_requires_hitl() -> None:
    state = {
        "tenant_id": "tenant-1",
        "job_id": "job-1",
        "session_id": None,
        "input": "Call the endpoint",
        "messages": [],
        "status": "running",
        "_llm_client": _FakeLLM(),
        "_model_alias": "default",
        "_system_prompt": "",
        "_agent_definition": {
            "id": "agent-1",
            "tools": ["rest_caller"],
            "hitl_tools": ["rest_caller"],
        },
        "_tool_registry": {"rest_caller": _FakeTool()},
        "_trace_callbacks": [],
        "_max_tool_steps": 1,
        "_max_tool_retries": 0,
    }

    result = await _tool_agent_step(state)

    assert result["status"] == "interrupted"
    assert result["pending_tool"] == "rest_caller"
    assert result["tool_args"] == {"url": "https://example.com"}
