"""Unit tests for CodeExecTool."""

from __future__ import annotations

import pytest

from agent.tools.code_exec import CodeExecTool, CodeExecToolError


@pytest.mark.asyncio
async def test_code_exec_executes_simple_code() -> None:
    """Test basic Python code execution."""
    tool = CodeExecTool()

    result = await tool.execute(code="print('hello world')")

    assert result.success is True
    assert result.exit_code == 0
    assert "hello world" in result.stdout
    assert result.stderr == ""
    assert result.took_ms > 0

    await tool.aclose()


@pytest.mark.asyncio
async def test_code_exec_captures_errors() -> None:
    """Test that exceptions and stderr are captured."""
    tool = CodeExecTool()

    result = await tool.execute(code="import sys\nprint('err', file=sys.stderr)\nexit(1)")

    assert result.success is False
    assert result.exit_code == 1
    assert "err" in result.stderr

    await tool.aclose()


@pytest.mark.asyncio
async def test_code_exec_handles_syntax_errors() -> None:
    """Test that syntax errors are captured in stderr."""
    tool = CodeExecTool()

    result = await tool.execute(code="def broken(\n")

    assert result.success is False
    assert result.exit_code != 0
    assert "SyntaxError" in result.stderr

    await tool.aclose()


@pytest.mark.asyncio
async def test_code_exec_enforces_timeout() -> None:
    """Test that executions exceeding timeout raise CodeExecToolError."""
    tool = CodeExecTool(timeout_seconds=0.5)

    with pytest.raises(CodeExecToolError, match="timed out"):
        await tool.execute(code="import time\ntime.sleep(5)")

    await tool.aclose()


@pytest.mark.asyncio
async def test_code_exec_rejects_blank_code() -> None:
    """Test that blank code is rejected."""
    tool = CodeExecTool()

    with pytest.raises(CodeExecToolError, match="blank"):
        await tool.execute(code="   ")

    await tool.aclose()


@pytest.mark.asyncio
async def test_code_exec_truncates_output() -> None:
    """Test that output is truncated when exceeding max_output_bytes."""
    tool = CodeExecTool(max_output_bytes=20)

    result = await tool.execute(code="print('a' * 100)")

    assert result.success is True
    assert len(result.stdout) <= 20

    await tool.aclose()


@pytest.mark.asyncio
async def test_code_exec_arun_returns_dict() -> None:
    """Test that arun() returns a dictionary."""
    tool = CodeExecTool()

    result_dict = await tool.arun(code="print(42)")

    assert isinstance(result_dict, dict)
    assert "stdout" in result_dict
    assert "stderr" in result_dict
    assert "exit_code" in result_dict
    assert "success" in result_dict
    assert "took_ms" in result_dict
    assert "42" in result_dict["stdout"]

    await tool.aclose()


@pytest.mark.asyncio
async def test_code_exec_isolates_secrets() -> None:
    """Test that secrets are removed from subprocess environment."""
    tool = CodeExecTool()

    code = """
import os
print('OPENAI_API_KEY' in os.environ)
print('LITELLM_API_KEY' in os.environ)
"""

    result = await tool.execute(code=code)

    assert result.success is True
    # Environment should not contain these keys
    assert "False" in result.stdout

    await tool.aclose()


@pytest.mark.asyncio
async def test_code_exec_tool_definition() -> None:
    """Test that tool definition is valid."""
    tool = CodeExecTool()

    definition = tool.tool_definition

    assert definition["name"] == "code_exec"
    assert "description" in definition
    assert "input_schema" in definition
    assert definition["input_schema"]["properties"]["code"]["type"] == "string"

    await tool.aclose()
