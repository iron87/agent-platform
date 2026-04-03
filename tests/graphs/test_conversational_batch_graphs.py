from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.graphs.batch_agent import _generate_batch_response
from agent.graphs.conversational import _generate_response


class _FakeLLM:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls: list[dict] = []

    async def create_completion(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.output),
                )
            ]
        )


@pytest.mark.asyncio
async def test_conversational_graph_fail_open_without_llm() -> None:
    result = await _generate_response(
        {
            "tenant_id": "tenant-1",
            "job_id": "job-1",
            "session_id": None,
            "input": "hello",
            "messages": [],
            "_llm_client": None,
            "_model_alias": "default",
            "_system_prompt": "",
            "_trace_callbacks": [],
            "_agent_definition": {},
        }
    )

    assert result["status"] == "completed"
    assert result["output"] == "Echo: hello"


@pytest.mark.asyncio
async def test_conversational_graph_uses_default_alias_for_unknown_model() -> None:
    fake_llm = _FakeLLM("ok")

    result = await _generate_response(
        {
            "tenant_id": "tenant-1",
            "job_id": "job-1",
            "session_id": "s1",
            "input": "hello",
            "messages": [],
            "_llm_client": fake_llm,
            "_model_alias": "unsupported-alias",
            "_system_prompt": "system",
            "_trace_callbacks": [],
            "_agent_definition": {"id": "agent-1"},
        }
    )

    assert result["output"] == "ok"
    assert fake_llm.calls[0]["model"] == "default"


@pytest.mark.asyncio
async def test_batch_graph_fail_open_without_llm() -> None:
    result = await _generate_batch_response(
        {
            "tenant_id": "tenant-1",
            "job_id": "job-1",
            "session_id": None,
            "input": "hello",
            "messages": [],
            "_llm_client": None,
            "_model_alias": "default",
            "_system_prompt": "",
            "_trace_callbacks": [],
            "_agent_definition": {},
        }
    )

    assert result["status"] == "completed"
    assert result["output"] == "Batch echo: hello"


@pytest.mark.asyncio
async def test_batch_graph_uses_default_alias_for_unknown_model() -> None:
    fake_llm = _FakeLLM("batch-ok")

    result = await _generate_batch_response(
        {
            "tenant_id": "tenant-1",
            "job_id": "job-1",
            "session_id": "s1",
            "input": "hello",
            "messages": [],
            "_llm_client": fake_llm,
            "_model_alias": "unsupported-alias",
            "_system_prompt": "system",
            "_trace_callbacks": [],
            "_agent_definition": {"id": "agent-1"},
        }
    )

    assert result["output"] == "batch-ok"
    assert fake_llm.calls[0]["model"] == "default"
