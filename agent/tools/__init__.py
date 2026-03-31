from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from agent.tools.code_exec import CodeExecTool, build_code_exec_tool
from agent.tools.file_ops import FileOpsTool, build_file_ops_tool
from agent.tools.rest_caller import RestCallerTool, build_rest_caller_tool
from agent.tools.web_search import WebSearchTool, build_web_search_tool

ToolInstance = WebSearchTool | CodeExecTool | RestCallerTool | FileOpsTool

TOOL_BUILDERS: dict[str, Any] = {
    "web_search": build_web_search_tool,
    "code_exec": build_code_exec_tool,
    "rest_caller": build_rest_caller_tool,
    "file_ops": build_file_ops_tool,
}


def build_tool_registry(*, tool_builders: dict[str, Any] | None = None) -> dict[str, ToolInstance]:
    """Build runtime tool registry from known builders.

    Args:
        tool_builders: Optional builder map for testing/overrides.

    Returns:
        Dict mapping tool names to instantiated tool objects.
    """
    builders = tool_builders or TOOL_BUILDERS
    return {tool_name: builder() for tool_name, builder in builders.items()}


def normalize_allowed_tool_names(agent_definition: dict[str, Any]) -> list[str]:
    """Extract and normalize allowed tool names from an agent definition.

    Supports both `tools` and `tool_names` to ease migration.
    """
    raw_tools = agent_definition.get("tools")
    if raw_tools is None:
        raw_tools = agent_definition.get("tool_names")

    if raw_tools is None:
        return []

    if not isinstance(raw_tools, Iterable) or isinstance(raw_tools, (str, bytes)):
        raise ValueError("agent definition tools must be a list of tool names")

    normalized: list[str] = []
    for item in raw_tools:
        tool_name = str(item).strip()
        if tool_name:
            normalized.append(tool_name)

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(normalized))


def get_allowed_tools(
    agent_definition: dict[str, Any],
    *,
    tool_registry: dict[str, ToolInstance] | None = None,
) -> dict[str, ToolInstance]:
    """Return the subset of tools allowed for a specific agent definition.

    An empty allowlist means no tools are allowed.
    """
    registry = tool_registry or build_tool_registry()
    allowed_names = normalize_allowed_tool_names(agent_definition)

    unknown = [name for name in allowed_names if name not in registry]
    if unknown:
        raise ValueError(f"unknown tool(s) in agent definition: {unknown}")

    return {name: registry[name] for name in allowed_names}


def build_openai_tools_payload(allowed_tools: dict[str, ToolInstance]) -> list[dict[str, Any]]:
    """Build OpenAI-compatible tool payload from tool definitions."""
    payload: list[dict[str, Any]] = []
    for tool in allowed_tools.values():
        payload.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
        )
    return payload


async def aclose_tools(tool_registry: dict[str, ToolInstance]) -> None:
    """Best-effort async cleanup of instantiated tools."""
    for tool in tool_registry.values():
        aclose = getattr(tool, "aclose", None)
        if callable(aclose):
            await aclose()


__all__ = [
    "TOOL_BUILDERS",
    "ToolInstance",
    "aclose_tools",
    "build_openai_tools_payload",
    "build_tool_registry",
    "get_allowed_tools",
    "normalize_allowed_tool_names",
]
