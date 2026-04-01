"""Tool-calling LangGraph with retry and fail handling."""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph

from agent.graphs.state import AgentState
from agent.llm import VALID_ALIASES
from agent.observability import emit_tool_call_span
from agent.tools import build_openai_tools_payload, build_tool_registry, get_allowed_tools


DEFAULT_MAX_TOOL_STEPS = 4
DEFAULT_MAX_TOOL_RETRIES = 2


class ToolExecutionError(RuntimeError):
    """Raised when tool execution fails after retries."""


class ToolLoopError(RuntimeError):
    """Raised when the tool loop cannot continue."""


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _message_to_dict(message: Any) -> dict[str, Any]:
    if hasattr(message, "model_dump"):
        return message.model_dump(exclude_unset=True)
    if isinstance(message, dict):
        return dict(message)

    payload: dict[str, Any] = {
        "role": _get_attr(message, "role", "assistant"),
        "content": _get_attr(message, "content", ""),
    }

    tool_calls = _get_attr(message, "tool_calls", None)
    if tool_calls:
        payload["tool_calls"] = [_tool_call_to_dict(tc) for tc in tool_calls]

    return payload


def _tool_call_to_dict(tool_call: Any) -> dict[str, Any]:
    if isinstance(tool_call, dict):
        return dict(tool_call)

    function = _get_attr(tool_call, "function", {})
    return {
        "id": _get_attr(tool_call, "id", "tool-call-unknown"),
        "type": _get_attr(tool_call, "type", "function"),
        "function": {
            "name": _get_attr(function, "name", ""),
            "arguments": _get_attr(function, "arguments", "{}"),
        },
    }


def _parse_tool_args(raw_arguments: str) -> dict[str, Any]:
    if not raw_arguments:
        return {}
    try:
        decoded = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise ToolLoopError(f"invalid tool arguments JSON: {exc}") from exc

    if not isinstance(decoded, dict):
        raise ToolLoopError("tool arguments must decode to an object")
    return decoded


async def _run_tool_with_retry(
    *,
    tool_name: str,
    tool: Any,
    args: dict[str, Any],
    callbacks: list[Any],
    max_retries: int,
) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        started_at = perf_counter()
        try:
            result = await tool.arun(**args)
            emit_tool_call_span(
                callbacks,
                tool_name=tool_name,
                args=args,
                output=result,
                error=None,
                attempt=attempt + 1,
                started_at=started_at,
            )
            return result
        except Exception as exc:  # pragma: no cover - exact exception type tool-specific
            last_error = exc
            emit_tool_call_span(
                callbacks,
                tool_name=tool_name,
                args=args,
                output=None,
                error=str(exc),
                attempt=attempt + 1,
                started_at=started_at,
            )

    raise ToolExecutionError(f"tool '{tool_name}' failed after {max_retries + 1} attempts: {last_error}")


def _resolve_model_alias(state: AgentState) -> str:
    requested_alias = str(state.get("_model_alias") or "default").strip()
    return requested_alias if requested_alias in VALID_ALIASES else "default"


async def _tool_agent_step(state: AgentState) -> dict[str, Any]:
    llm_client = state.get("_llm_client")
    model_alias = _resolve_model_alias(state)
    system_prompt = str(state.get("_system_prompt") or "")
    max_tool_steps = int(state.get("_max_tool_steps") or DEFAULT_MAX_TOOL_STEPS)
    max_tool_retries = int(state.get("_max_tool_retries") or DEFAULT_MAX_TOOL_RETRIES)
    callbacks = list(state.get("_trace_callbacks") or [])

    if llm_client is None:
        return {
            "output": f"Echo: {state['input']}",
            "status": "completed",
            "error": None,
        }

    agent_definition = dict(state.get("_agent_definition") or {})
    tool_registry = dict(state.get("_tool_registry") or build_tool_registry())
    allowed_tools = get_allowed_tools(agent_definition, tool_registry=tool_registry)
    tools_payload = build_openai_tools_payload(allowed_tools)

    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    existing_messages = state.get("messages") or []
    for msg in existing_messages:
        if isinstance(msg, dict):
            messages.append(msg)

    messages.append({"role": "user", "content": state["input"]})

    tool_events: list[dict[str, Any]] = []

    for _ in range(max_tool_steps):
        completion = await llm_client.create_completion(
            model=model_alias,
            messages=messages,
            tools=tools_payload or None,
            tool_choice="auto" if tools_payload else None,
            trace_callbacks=callbacks,
            trace_context={
                "tenant_id": state.get("tenant_id"),
                "agent_id": agent_definition.get("id"),
                "job_id": state.get("job_id"),
                "session_id": state.get("session_id"),
            },
        )

        choice = completion.choices[0]
        message = choice.message
        finish_reason = _get_attr(choice, "finish_reason", None)
        tool_calls = _get_attr(message, "tool_calls", None)

        if finish_reason != "tool_calls" or not tool_calls:
            final_message = _get_attr(message, "content", "") or ""
            return {
                "messages": messages,
                "output": final_message,
                "status": "completed",
                "error": None,
                "tool_events": tool_events,
            }

        messages.append(_message_to_dict(message))

        for raw_tool_call in tool_calls:
            tool_call = _tool_call_to_dict(raw_tool_call)
            tool_name = str(_get_attr(tool_call.get("function", {}), "name", "")).strip()
            args = _parse_tool_args(str(_get_attr(tool_call.get("function", {}), "arguments", "{}")))

            if tool_name not in allowed_tools:
                error_text = f"tool '{tool_name}' is not in allowlist"
                tool_events.append({"tool": tool_name, "success": False, "error": error_text})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "tool-call-unknown"),
                        "name": tool_name,
                        "content": json.dumps({"error": error_text}),
                    }
                )
                continue

            tool = allowed_tools[tool_name]
            try:
                tool_result = await _run_tool_with_retry(
                    tool_name=tool_name,
                    tool=tool,
                    args=args,
                    callbacks=callbacks,
                    max_retries=max_tool_retries,
                )
                tool_events.append({"tool": tool_name, "success": True})
                tool_payload = tool_result
            except ToolExecutionError as exc:
                tool_events.append({"tool": tool_name, "success": False, "error": str(exc)})
                tool_payload = {"error": str(exc)}

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", "tool-call-unknown"),
                    "name": tool_name,
                    "content": json.dumps(tool_payload, default=str),
                }
            )

    return {
        "messages": messages,
        "output": "Tool loop reached max steps without final answer.",
        "status": "failed",
        "error": "tool loop exhausted",
        "tool_events": tool_events,
    }


def build_tool_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("tool_agent_step", _tool_agent_step)
    graph.add_edge(START, "tool_agent_step")
    graph.add_edge("tool_agent_step", END)
    return graph.compile()


__all__ = [
    "DEFAULT_MAX_TOOL_RETRIES",
    "DEFAULT_MAX_TOOL_STEPS",
    "ToolExecutionError",
    "ToolLoopError",
    "build_tool_agent_graph",
]
