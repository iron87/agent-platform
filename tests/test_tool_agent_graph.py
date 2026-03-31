"""Unit tests for tool-agent graph loop, retries, and allowlist handling."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from agent.graphs.tool_agent import build_tool_agent_graph


class FlakyTool:
    name = "flaky"
    description = "Flaky test tool"
    input_schema = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
    }

    def __init__(self, fail_times: int = 0) -> None:
        self.fail_times = fail_times
        self.calls = 0

    async def arun(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("temporary tool failure")
        return {"ok": True, "echo": kwargs}


class FakeLLM:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = responses
        self.calls = 0

    async def create_completion(self, **kwargs):
        response = self._responses[self.calls]
        self.calls += 1
        return response



def _completion_with_tool_call(*, name: str, args: dict, call_id: str = "call-1") -> SimpleNamespace:
    tool_call = SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )
    message = SimpleNamespace(role="assistant", content=None, tool_calls=[tool_call])
    choice = SimpleNamespace(message=message, finish_reason="tool_calls")
    return SimpleNamespace(choices=[choice])



def _completion_with_text(content: str) -> SimpleNamespace:
    message = SimpleNamespace(role="assistant", content=content, tool_calls=[])
    choice = SimpleNamespace(message=message, finish_reason="stop")
    return SimpleNamespace(choices=[choice])


@pytest.mark.asyncio
async def test_tool_agent_retries_then_succeeds() -> None:
    graph = build_tool_agent_graph()
    flaky_tool = FlakyTool(fail_times=1)

    llm = FakeLLM(
        responses=[
            _completion_with_tool_call(name="flaky", args={"value": 42}),
            _completion_with_text("done"),
        ]
    )

    state = {
        "client_id": "tenant-1",
        "job_id": "job-1",
        "session_id": None,
        "input": "run tool",
        "messages": [],
        "pending_tool": None,
        "tool_args": None,
        "tool_result": None,
        "output": None,
        "status": "running",
        "approved": None,
        "error": None,
        "_llm_client": llm,
        "_model_alias": "fast",
        "_system_prompt": "",
        "_agent_definition": {"tools": ["flaky"]},
        "_tool_registry": {"flaky": flaky_tool},
        "_trace_callbacks": [],
        "_max_tool_steps": 3,
        "_max_tool_retries": 2,
    }

    result = await graph.ainvoke(state)

    assert result["status"] == "completed"
    assert result["error"] is None
    assert result["output"] == "done"
    assert flaky_tool.calls == 2
    assert result["tool_events"][0]["success"] is True


@pytest.mark.asyncio
async def test_tool_agent_blocks_disallowed_tool() -> None:
    graph = build_tool_agent_graph()
    llm = FakeLLM(
        responses=[
            _completion_with_tool_call(name="not_allowed", args={}),
            _completion_with_text("final after blocked tool"),
        ]
    )

    state = {
        "client_id": "tenant-1",
        "job_id": "job-2",
        "session_id": None,
        "input": "try disallowed tool",
        "messages": [],
        "pending_tool": None,
        "tool_args": None,
        "tool_result": None,
        "output": None,
        "status": "running",
        "approved": None,
        "error": None,
        "_llm_client": llm,
        "_model_alias": "fast",
        "_system_prompt": "",
        "_agent_definition": {"tools": ["web_search"]},
        "_tool_registry": {},
        "_trace_callbacks": [],
        "_max_tool_steps": 3,
        "_max_tool_retries": 1,
    }

    result = await graph.ainvoke(state)

    assert result["status"] == "completed"
    assert result["output"] == "final after blocked tool"
    assert result["tool_events"][0]["success"] is False
    assert "allowlist" in result["tool_events"][0]["error"]


@pytest.mark.asyncio
async def test_tool_agent_fails_when_loop_exhausted() -> None:
    graph = build_tool_agent_graph()
    llm = FakeLLM(
        responses=[
            _completion_with_tool_call(name="not_allowed", args={}),
            _completion_with_tool_call(name="not_allowed", args={}),
        ]
    )

    state = {
        "client_id": "tenant-1",
        "job_id": "job-3",
        "session_id": None,
        "input": "never finish",
        "messages": [],
        "pending_tool": None,
        "tool_args": None,
        "tool_result": None,
        "output": None,
        "status": "running",
        "approved": None,
        "error": None,
        "_llm_client": llm,
        "_model_alias": "fast",
        "_system_prompt": "",
        "_agent_definition": {"tools": ["web_search"]},
        "_tool_registry": {},
        "_trace_callbacks": [],
        "_max_tool_steps": 2,
        "_max_tool_retries": 0,
    }

    result = await graph.ainvoke(state)

    assert result["status"] == "failed"
    assert result["error"] == "tool loop exhausted"
