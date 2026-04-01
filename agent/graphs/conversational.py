"""Conversational graph with session-context-aware message construction."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agent.graphs.state import AgentState


def _normalize_messages(messages: list[Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for msg in messages:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            normalized.append({"role": str(msg["role"]), "content": str(msg["content"])})
    return normalized


async def _generate_response(state: AgentState) -> dict[str, Any]:
    llm_client = state.get("_llm_client")
    model_alias = str(state.get("_model_alias") or "default")
    system_prompt = str(state.get("_system_prompt") or "")
    callbacks = list(state.get("_trace_callbacks") or [])
    agent_definition = dict(state.get("_agent_definition") or {})

    messages = _normalize_messages(state.get("messages", []))
    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}, *messages]
    messages.append({"role": "user", "content": state["input"]})

    if llm_client is None:
        # Fail-open fallback for tests or minimal environments.
        output = f"Echo: {state['input']}"
    else:
        completion = await llm_client.create_completion(
            model=model_alias,
            messages=messages,
            trace_callbacks=callbacks,
            trace_context={
                "tenant_id": state.get("tenant_id"),
                "agent_id": agent_definition.get("id"),
                "job_id": state.get("job_id"),
                "session_id": state.get("session_id"),
            },
        )
        output = completion.choices[0].message.content or ""

    return {
        "messages": [
            {"role": "user", "content": state["input"]},
            {"role": "assistant", "content": output},
        ],
        "output": output,
        "status": "completed",
        "error": None,
    }


def build_conversational_graph():
    graph = StateGraph(AgentState)
    graph.add_node("generate_response", _generate_response)
    graph.add_edge(START, "generate_response")
    graph.add_edge("generate_response", END)
    return graph.compile()


__all__ = ["build_conversational_graph"]
