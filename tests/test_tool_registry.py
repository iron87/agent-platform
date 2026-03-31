"""Unit tests for tool registry and allowlist behavior."""

from __future__ import annotations

import pytest

from agent.tools import (
    TOOL_BUILDERS,
    build_openai_tools_payload,
    build_tool_registry,
    get_allowed_tools,
    normalize_allowed_tool_names,
)


def test_build_tool_registry_contains_expected_tools() -> None:
    registry = build_tool_registry()

    assert set(registry.keys()) == set(TOOL_BUILDERS.keys())
    assert "web_search" in registry
    assert "code_exec" in registry
    assert "rest_caller" in registry
    assert "file_ops" in registry


def test_normalize_allowed_tool_names_supports_tools_field() -> None:
    names = normalize_allowed_tool_names({"tools": ["web_search", "code_exec", "web_search"]})

    assert names == ["web_search", "code_exec"]


def test_normalize_allowed_tool_names_supports_tool_names_field() -> None:
    names = normalize_allowed_tool_names({"tool_names": ["rest_caller", "file_ops"]})

    assert names == ["rest_caller", "file_ops"]


def test_normalize_allowed_tool_names_empty_when_missing() -> None:
    names = normalize_allowed_tool_names({"name": "no-tools-agent"})

    assert names == []


def test_normalize_allowed_tool_names_rejects_string() -> None:
    with pytest.raises(ValueError, match="must be a list"):
        normalize_allowed_tool_names({"tools": "web_search"})


def test_get_allowed_tools_filters_registry() -> None:
    registry = build_tool_registry()

    allowed = get_allowed_tools({"tools": ["web_search", "code_exec"]}, tool_registry=registry)

    assert set(allowed.keys()) == {"web_search", "code_exec"}



def test_get_allowed_tools_rejects_unknown_tool() -> None:
    registry = build_tool_registry()

    with pytest.raises(ValueError, match="unknown tool"):
        get_allowed_tools({"tools": ["web_search", "not_real_tool"]}, tool_registry=registry)


def test_build_openai_tools_payload_shape() -> None:
    registry = build_tool_registry()
    allowed = get_allowed_tools({"tools": ["web_search"]}, tool_registry=registry)

    payload = build_openai_tools_payload(allowed)

    assert len(payload) == 1
    assert payload[0]["type"] == "function"
    assert payload[0]["function"]["name"] == "web_search"
    assert "parameters" in payload[0]["function"]
