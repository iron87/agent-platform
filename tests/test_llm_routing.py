from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from agent.graphs.conversational import build_conversational_graph
from agent.llm import LiteLLMClient
from agent.repositories.agents import AgentsRepository


class _StubRepo:
    def __init__(self, record):
        self._record = record

    async def get_by_id(self, _agent_id):
        return self._record


class _RecordingCallback:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def on_custom_event(self, *, name: str, data: dict) -> None:
        self.events.append((name, data))


class _RecordingLLM:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create_completion(self, *, model, messages, **kwargs):
        self.calls.append({"model": model, "messages": messages, "kwargs": kwargs})
        return SimpleNamespace(
            model=model,
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=f"response-via-{model}"),
                )
            ],
        )


@pytest.mark.asyncio
async def test_agents_repository_rejects_unknown_model_alias() -> None:
    repo = AgentsRepository.__new__(AgentsRepository)
    repo._repo = _StubRepo(
        {
            "id": uuid4(),
            "name": "broken-agent",
            "model_alias": "provider/direct-model",
            "prompt_file": "examples/prompts/us2_support_prompt.txt",
            "graph_type": "conversational",
        }
    )

    with pytest.raises(Exception, match="model_alias"):
        await repo.get_by_id(uuid4())


@pytest.mark.asyncio
async def test_litellm_client_emits_fallback_event_from_raw_response_headers() -> None:
    client = LiteLLMClient(base_url="http://litellm:4000/v1", api_key="test-key")
    callback = _RecordingCallback()

    parsed_response = SimpleNamespace(
        model="fast",
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content="Fallback answer"),
            )
        ],
    )
    raw_response = SimpleNamespace(
        headers={
            "x-litellm-fallback-from": "default",
            "x-litellm-fallback-to": "fast",
            "x-litellm-fallback-reason": "primary_timeout",
            "x-litellm-model-id": "openai/gpt-4o-mini",
        },
        parse=lambda: parsed_response,
    )

    async def fake_create(*, model, messages, **kwargs):
        assert model == "default"
        assert messages[-1]["content"] == "hello"
        assert "trace_callbacks" not in kwargs
        assert "trace_context" not in kwargs
        return raw_response

    client._client.chat.completions = SimpleNamespace(
        with_raw_response=SimpleNamespace(create=fake_create)
    )

    response = await client.create_completion(
        model="default",
        messages=[{"role": "user", "content": "hello"}],
        trace_callbacks=[callback],
        trace_context={"tenant_id": "tenant-demo", "agent_id": "agent-demo"},
    )

    assert response is parsed_response
    assert callback.events == [
        (
            "llm_fallback",
            {
                "requested_alias": "default",
                "fallback_from": "default",
                "fallback_to": "fast",
                "reason": "primary_timeout",
                "provider_model": "openai/gpt-4o-mini",
                "tenant_id": "tenant-demo",
                "agent_id": "agent-demo",
            },
        )
    ]


def test_env_example_documents_alias_and_tenant_budget_controls() -> None:
    env_example = Path("infra/.env.example").read_text(encoding="utf-8")

    assert "LITELLM_BUDGET_DEFAULT=" in env_example
    assert "LITELLM_BUDGET_FAST=" in env_example
    assert "LITELLM_BUDGET_EMBEDDING=" in env_example
    assert "LITELLM_TENANT_BUDGET_TOTAL=" in env_example
    assert "LITELLM_TENANT_BUDGET_DURATION=" in env_example


@pytest.mark.asyncio
async def test_conversational_graph_uses_alias_from_state() -> None:
    llm = _RecordingLLM()
    graph = build_conversational_graph()

    result = await graph.ainvoke(
        {
            "tenant_id": "tenant-demo",
            "job_id": "job-demo",
            "session_id": None,
            "input": "hello",
            "messages": [],
            "pending_tool": None,
            "tool_args": None,
            "tool_result": None,
            "tool_events": None,
            "output": None,
            "status": "running",
            "approved": None,
            "error": None,
            "_llm_client": llm,
            "_model_alias": "fast",
            "_system_prompt": "system",
            "_agent_definition": {"id": "agent-demo"},
            "_trace_callbacks": [],
        }
    )

    assert result["output"] == "response-via-fast"
    assert llm.calls[0]["model"] == "fast"


@pytest.mark.asyncio
async def test_batch_graph_uses_alias_from_state() -> None:
    from agent.graphs.batch_agent import build_batch_agent_graph

    llm = _RecordingLLM()
    graph = build_batch_agent_graph()

    result = await graph.ainvoke(
        {
            "tenant_id": "tenant-demo",
            "job_id": "job-batch",
            "session_id": None,
            "input": "summarize batch results",
            "messages": [],
            "pending_tool": None,
            "tool_args": None,
            "tool_result": None,
            "tool_events": None,
            "output": None,
            "status": "running",
            "approved": None,
            "error": None,
            "_llm_client": llm,
            "_model_alias": "default",
            "_system_prompt": "batch system",
            "_agent_definition": {"id": "agent-batch"},
            "_trace_callbacks": [],
        }
    )

    assert result["output"] == "response-via-default"
    assert llm.calls[0]["model"] == "default"
