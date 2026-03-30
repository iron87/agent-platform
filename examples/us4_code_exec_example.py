#!/usr/bin/env python3
"""US4 example: code execution tool, with two runnable modes.

MODE 1 — tool only (default, no LLM required):
    python examples/us4_code_exec_example.py
    CODE_TO_EXECUTE="print('hello')" python examples/us4_code_exec_example.py

    Calls CodeExecTool.execute() directly and prints formatted results.
    No LiteLLM or API key needed. Useful for testing code safety + sandboxing.

MODE 2 — full LLM + tool loop (requires LiteLLM stack running):
    WITH_LLM=1 python examples/us4_code_exec_example.py

    The LLM receives a task description and a function definition for code_exec.
    If it decides to write and run code, the tool executes in an isolated subprocess.
    The result is fed back to the LLM, which can iterate (generate → execute → refine).
    Requires LITELLM_BASE_URL and LITELLM_API_KEY in the environment (or .env).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from textwrap import dedent

from agent.tools.code_exec import CodeExecTool, CodeExecToolError, format_code_exec_result


# ── Mode 1: tool only ──────────────────────────────────────────────────────────

async def _run_tool_only() -> int:
    code = os.getenv(
        "CODE_TO_EXECUTE",
        dedent("""
            import math
            numbers = [1, 2, 3, 4, 5]
            result = sum(x**2 for x in numbers)
            print(f"Sum of squares: {result}")
        """).strip(),
    )
    timeout_seconds = float(os.getenv("CODE_EXEC_TIMEOUT_SECONDS", "10"))
    max_output_bytes = int(os.getenv("CODE_EXEC_MAX_OUTPUT_BYTES", "10240"))

    print(f"[tool-only] executing code:\n{code}\n")
    tool = CodeExecTool(timeout_seconds=timeout_seconds, max_output_bytes=max_output_bytes)
    try:
        response = await tool.execute(code=code)
    except CodeExecToolError as exc:
        print(f"code execution failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await tool.aclose()

    print(format_code_exec_result(response))
    return 0


# ── Mode 2: LLM decides → code executes → LLM iterates ────────────────────────

async def _run_with_llm() -> int:
    litellm_base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1")
    litellm_api_key = os.getenv("LITELLM_API_KEY", "")
    task = os.getenv(
        "CODE_TASK",
        "Write Python code to calculate the factorial of 5 and print the result.",
    )
    max_output_bytes = int(os.getenv("CODE_EXEC_MAX_OUTPUT_BYTES", "5120"))

    if not litellm_api_key:
        print("Set LITELLM_API_KEY before running with WITH_LLM=1.", file=sys.stderr)
        return 1

    from agent.llm import LiteLLMClient

    llm = LiteLLMClient(base_url=litellm_base_url, api_key=litellm_api_key)
    tool = CodeExecTool(max_output_bytes=max_output_bytes)

    # ── Step 1: send task + tool definition to the LLM ────────────────────────
    tool_spec = {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        },
    }
    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are a Python coding assistant. "
                "When given a task, write Python code to solve it and execute it using the code_exec tool. "
                "If the code fails, analyze the error and try again with a fix. "
                "Always answer in English."
            ),
        },
        {"role": "user", "content": task},
    ]

    print(f"[with-llm] task: {task!r}")
    print("[with-llm] step 1 — asking LLM to write and execute code ...\n")

    try:
        resp1 = await llm.create_completion(
            model="fast",
            messages=messages,
            tools=[tool_spec],
            tool_choice="auto",
        )
    except Exception as exc:
        print(f"LLM call failed: {exc}", file=sys.stderr)
        await tool.aclose()
        return 1

    choice = resp1.choices[0]

    if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
        # LLM answered directly without calling the tool
        print("[with-llm] LLM answered without tool call:")
        print(choice.message.content or "")
        await tool.aclose()
        return 0

    # ── Step 2: execute the code the LLM generated ────────────────────────────
    tool_call = choice.message.tool_calls[0]
    args = json.loads(tool_call.function.arguments)
    generated_code = args.get("code", "")
    print(f"[with-llm] step 2 — generated code:\n{generated_code}\n")

    try:
        exec_result = await tool.arun(**args)
    except CodeExecToolError as exc:
        print(f"code execution failed: {exc}", file=sys.stderr)
        await tool.aclose()
        return 1
    finally:
        await tool.aclose()

    # ── Step 3: feed execution result back → LLM summarises ──────────────────
    messages.append(choice.message.model_dump(exclude_unset=True))
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": tool_call.function.name,
            "content": json.dumps(exec_result, default=str),
        }
    )

    print("[with-llm] step 3 — feeding execution result back to LLM ...\n")
    try:
        resp2 = await llm.create_completion(model="fast", messages=messages)
    except Exception as exc:
        print(f"LLM synthesis call failed: {exc}", file=sys.stderr)
        return 1

    print("[with-llm] LLM summary:")
    print(resp2.choices[0].message.content or "")
    return 0


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> int:
    if os.getenv("WITH_LLM"):
        return asyncio.run(_run_with_llm())
    return asyncio.run(_run_tool_only())


if __name__ == "__main__":
    raise SystemExit(main())
