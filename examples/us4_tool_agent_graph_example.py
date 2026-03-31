#!/usr/bin/env python3
"""US4 example: tool-agent graph loop with retries and tool-call observability.

MODE 1 - deterministic local run (default):
    python examples/us4_tool_agent_graph_example.py

MODE 2 - with LiteLLM:
    WITH_LLM=1 LITELLM_BASE_URL=http://localhost:4000/v1 LITELLM_API_KEY=... python examples/us4_tool_agent_graph_example.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace

from agent.graphs.tool_agent import build_tool_agent_graph
from agent.tools import build_tool_registry


class RecordingCallback:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def on_custom_event(self, *, name: str, data: dict) -> None:
        if name == "tool_call":
            self.events.append(data)


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def create_completion(self, **kwargs):
        self.calls += 1

        if self.calls == 1:
            tool_call = SimpleNamespace(
                id="call-1",
                type="function",
                function=SimpleNamespace(
                    name="code_exec",
                    arguments=json.dumps({"code": "print(sum(i*i for i in range(1, 6)))"}),
                ),
            )
            message = SimpleNamespace(role="assistant", content=None, tool_calls=[tool_call])
            return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="tool_calls")])

        message = SimpleNamespace(
            role="assistant",
            content="I executed the code and obtained the result from the tool call.",
            tool_calls=[],
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])


async def _run_local_deterministic() -> int:
    callback = RecordingCallback()
    graph = build_tool_agent_graph()
    tools = build_tool_registry()

    state = {
        "tenant_id": "demo-tenant",
        "job_id": "demo-job",
        "session_id": None,
        "input": "Compute the sum of squares from 1 to 5.",
        "messages": [],
        "pending_tool": None,
        "tool_args": None,
        "tool_result": None,
        "output": None,
        "status": "running",
        "approved": None,
        "error": None,
        "_llm_client": FakeLLM(),
        "_model_alias": "fast",
        "_system_prompt": "Use tools when needed.",
        "_agent_definition": {"tools": ["code_exec"]},
        "_tool_registry": tools,
        "_trace_callbacks": [callback],
        "_max_tool_steps": 3,
        "_max_tool_retries": 1,
    }

    result = await graph.ainvoke(state)

    print("=== Tool Agent Result ===")
    print("status:", result.get("status"))
    print("error:", result.get("error"))
    print("output:", result.get("output"))
    print()
    print("=== Tool Events (Graph) ===")
    for item in result.get("tool_events", []):
        print(item)
    print()
    print("=== Tool Spans (Observability Callback) ===")
    for event in callback.events:
        print(event)

    return 0 if result.get("status") == "completed" else 1


async def _run_with_llm() -> int:
    litellm_base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1")
    litellm_api_key = os.getenv("LITELLM_API_KEY", "")
    prompt = os.getenv(
        "TOOL_AGENT_TASK",
        "Use the code_exec tool to compute the sum of squares from 1 to 5, then answer briefly.",
    )

    if not litellm_api_key:
        print("Set LITELLM_API_KEY before running with WITH_LLM=1.", file=sys.stderr)
        return 1

    from agent.llm import LiteLLMClient

    callback = RecordingCallback()
    graph = build_tool_agent_graph()
    tools = build_tool_registry()

    state = {
        "tenant_id": "demo-tenant",
        "job_id": "demo-job-llm",
        "session_id": None,
        "input": prompt,
        "messages": [],
        "pending_tool": None,
        "tool_args": None,
        "tool_result": None,
        "output": None,
        "status": "running",
        "approved": None,
        "error": None,
        "_llm_client": LiteLLMClient(base_url=litellm_base_url, api_key=litellm_api_key),
        "_model_alias": "fast",
        "_system_prompt": "You are concise. Use available tools when they help.",
        "_agent_definition": {"tools": ["code_exec", "web_search", "rest_caller", "file_ops"]},
        "_tool_registry": tools,
        "_trace_callbacks": [callback],
        "_max_tool_steps": 4,
        "_max_tool_retries": 1,
    }

    result = await graph.ainvoke(state)

    print("=== Tool Agent Result ===")
    print("status:", result.get("status"))
    print("error:", result.get("error"))
    print("output:", result.get("output"))
    print()
    print("=== Tool Events (Graph) ===")
    for item in result.get("tool_events", []):
        print(item)
    print()
    print("=== Tool Spans (Observability Callback) ===")
    for event in callback.events:
        print(event)

    return 0 if result.get("status") == "completed" else 1


def main() -> int:
    if os.getenv("WITH_LLM"):
        return asyncio.run(_run_with_llm())
    return asyncio.run(_run_local_deterministic())


if __name__ == "__main__":
    raise SystemExit(main())
