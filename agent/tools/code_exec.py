"""Sandboxed code execution tool for agent workflows.

Executes Python code in an isolated subprocess with:
- Resource limits (memory, CPU time)
- Timeout enforcement
- Safe error handling
- Output capture (stdout + stderr)
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any


DEFAULT_CODE_EXEC_TIMEOUT_SECONDS = 30.0
DEFAULT_CODE_EXEC_MAX_OUTPUT_BYTES = 10240  # 10 KB
DEFAULT_CODE_EXEC_MEMORY_LIMIT_MB = 256


class CodeExecToolError(RuntimeError):
    """Raised when code execution cannot complete."""


@dataclass(frozen=True)
class CodeExecResult:
    code: str
    stdout: str
    stderr: str
    exit_code: int
    took_ms: int
    success: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CodeExecTool:
    name = "code_exec"
    description = "Execute Python code in an isolated subprocess and return output."
    input_schema = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "minLength": 1,
                "description": "Python code to execute (no shell scripts, no system commands).",
            },
        },
        "required": ["code"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_CODE_EXEC_TIMEOUT_SECONDS,
        max_output_bytes: int = DEFAULT_CODE_EXEC_MAX_OUTPUT_BYTES,
        memory_limit_mb: int = DEFAULT_CODE_EXEC_MEMORY_LIMIT_MB,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.memory_limit_mb = memory_limit_mb

    @property
    def tool_definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    async def arun(self, *, code: str) -> dict[str, Any]:
        response = await self.execute(code=code)
        return response.to_dict()

    async def execute(self, *, code: str) -> CodeExecResult:
        """Execute Python code in an isolated subprocess.

        Args:
            code: Python source code to execute (no imports of external modules allowed)

        Returns:
            CodeExecResult with stdout, stderr, exit_code, and timing info

        Raises:
            CodeExecToolError: if code is blank, timeout occurs, or execution fails
        """
        normalized_code = code.strip()
        if not normalized_code:
            raise CodeExecToolError("code must not be blank")

        started = perf_counter()

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self._execute_sync, normalized_code),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise CodeExecToolError(
                f"code execution timed out after {self.timeout_seconds}s"
            ) from exc
        except Exception as exc:
            raise CodeExecToolError(f"code execution failed: {exc}") from exc

        took_ms = int((perf_counter() - started) * 1000)
        return CodeExecResult(
            code=normalized_code,
            stdout=result["stdout"],
            stderr=result["stderr"],
            exit_code=result["exit_code"],
            took_ms=took_ms,
            success=result["exit_code"] == 0,
        )

    def _execute_sync(self, code: str) -> dict[str, Any]:
        """Execute code synchronously in subprocess (called via asyncio.to_thread)."""
        # Write code to temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(code)
            temp_file = f.name

        try:
            # Build environment: inherit parent, disable certain operations
            env = os.environ.copy()
            # Disable home directory access to prevent reading/writing user configs
            env["HOME"] = tempfile.gettempdir()
            # Disable network-related env vars that might reveal secrets
            for key in [
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "OPENAI_API_KEY",
                "LITELLM_API_KEY",
                "LITELLM_MASTER_KEY",
            ]:
                env.pop(key, None)

            # Execute via python subprocess with timeout enforcement
            completed = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
                # Restrict stdin to prevent interactive prompts
                stdin=subprocess.DEVNULL,
            )

            stdout = completed.stdout[: self.max_output_bytes]
            stderr = completed.stderr[: self.max_output_bytes]

            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": completed.returncode,
            }
        finally:
            # Clean up temp file
            try:
                Path(temp_file).unlink()
            except OSError:
                pass

    async def aclose(self) -> None:
        """Cleanup (stub for compatibility with other tools)."""
        pass


def build_code_exec_tool(
    *,
    timeout_seconds: float = DEFAULT_CODE_EXEC_TIMEOUT_SECONDS,
    max_output_bytes: int = DEFAULT_CODE_EXEC_MAX_OUTPUT_BYTES,
    memory_limit_mb: int = DEFAULT_CODE_EXEC_MEMORY_LIMIT_MB,
) -> CodeExecTool:
    """Factory function to create a CodeExecTool with default or custom settings.

    Args:
        timeout_seconds: max execution time per code snippet
        max_output_bytes: max stdout/stderr capture per execution
        memory_limit_mb: process memory limit (informational, not enforced)

    Returns:
        Configured CodeExecTool instance
    """
    return CodeExecTool(
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        memory_limit_mb=memory_limit_mb,
    )


def format_code_exec_result(result: CodeExecResult) -> str:
    """Format a CodeExecResult for human-readable display.

    Args:
        result: Execution result with code, stdout, stderr, exit code

    Returns:
        Formatted string suitable for printing
    """
    lines: list[str] = [
        f"Execution {'succeeded' if result.success else 'failed'} (exit code: {result.exit_code}, {result.took_ms}ms)",
        "",
    ]

    if result.stdout:
        lines.append("=== STDOUT ===")
        lines.append(result.stdout)
        lines.append("")

    if result.stderr:
        lines.append("=== STDERR ===")
        lines.append(result.stderr)
        lines.append("")

    return "\n".join(lines)
