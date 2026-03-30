#!/usr/bin/env python3
"""US4 example: sandboxed file operations, with two runnable modes.

MODE 1 — tool only (default):
    python examples/us4_file_ops_example.py

MODE 2 — full LLM + tool loop:
    WITH_LLM=1 python examples/us4_file_ops_example.py

Mode 1 demonstrates write/read/list/delete in a sandbox directory.
Mode 2 lets the LLM decide file_ops calls and summarize results.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from tempfile import gettempdir

from agent.tools.file_ops import FileOpsTool, FileOpsToolError, format_file_ops_response


async def _run_tool_only() -> int:
    sandbox_root = os.getenv("FILE_OPS_ROOT_DIR", os.path.join(gettempdir(), "2brain_file_ops_example"))
    tool = FileOpsTool(root_dir=sandbox_root)

    print(f"[tool-only] sandbox root: {sandbox_root}")

    try:
        print("\n[1] make_dir docs")
        res1 = await tool.execute(action="make_dir", path="docs")
        print(format_file_ops_response(res1))

        print("\n[2] write_file docs/note.txt")
        res2 = await tool.execute(action="write_file", path="docs/note.txt", content="Hello from file_ops example")
        print(format_file_ops_response(res2))

        print("\n[3] read_file docs/note.txt")
        res3 = await tool.execute(action="read_file", path="docs/note.txt")
        print(format_file_ops_response(res3))

        print("\n[4] list_dir docs")
        res4 = await tool.execute(action="list_dir", path="docs")
        print(format_file_ops_response(res4))

        print("\n[5] delete_path docs recursively")
        res5 = await tool.execute(action="delete_path", path="docs", recursive=True)
        print(format_file_ops_response(res5))
    except FileOpsToolError as exc:
        print(f"file_ops failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await tool.aclose()

    return 0


async def _run_with_llm() -> int:
    litellm_base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1")
    litellm_api_key = os.getenv("LITELLM_API_KEY", "")
    task = os.getenv(
        "FILE_OPS_TASK",
        "Create a file docs/todo.txt with two TODO items, then read it and summarize the content.",
    )
    sandbox_root = os.getenv("FILE_OPS_ROOT_DIR", os.path.join(gettempdir(), "2brain_file_ops_example"))

    if not litellm_api_key:
        print("Set LITELLM_API_KEY before running with WITH_LLM=1.", file=sys.stderr)
        return 1

    from agent.llm import LiteLLMClient

    llm = LiteLLMClient(base_url=litellm_base_url, api_key=litellm_api_key)
    tool = FileOpsTool(root_dir=sandbox_root)

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
                "You are a concise assistant. "
                "Use file_ops to manipulate files in the sandbox when needed. "
                "Always answer in English."
            ),
        },
        {"role": "user", "content": task},
    ]

    print(f"[with-llm] task: {task!r}")
    print(f"[with-llm] sandbox root: {sandbox_root}")
    print("[with-llm] step 1 — asking LLM ...\n")

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
        print("[with-llm] LLM answered without tool call:")
        print(choice.message.content or "")
        await tool.aclose()
        return 0

    tool_call = choice.message.tool_calls[0]
    args = json.loads(tool_call.function.arguments)
    print(f"[with-llm] step 2 — LLM called '{tool_call.function.name}' with args: {args}")

    try:
        tool_result = await tool.arun(**args)
    except FileOpsToolError as exc:
        print(f"file_ops failed: {exc}", file=sys.stderr)
        await tool.aclose()
        return 1
    finally:
        await tool.aclose()

    messages.append(choice.message.model_dump(exclude_unset=True))
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": tool_call.function.name,
            "content": json.dumps(tool_result, default=str),
        }
    )

    print("[with-llm] step 3 — sending tool output back to LLM ...\n")
    try:
        resp2 = await llm.create_completion(model="fast", messages=messages)
    except Exception as exc:
        print(f"LLM synthesis call failed: {exc}", file=sys.stderr)
        return 1

    print("[with-llm] final answer:")
    print(resp2.choices[0].message.content or "")
    return 0


def main() -> int:
    if os.getenv("WITH_LLM"):
        return asyncio.run(_run_with_llm())
    return asyncio.run(_run_tool_only())


if __name__ == "__main__":
    raise SystemExit(main())
