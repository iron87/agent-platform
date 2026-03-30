#!/usr/bin/env python3
"""US4 example: REST caller tool, with two runnable modes.

MODE 1 — tool only (default, no LLM required):
    python examples/us4_rest_caller_example.py
    REST_URL="https://httpbin.org/get" python examples/us4_rest_caller_example.py

MODE 2 — full LLM + tool loop (requires LiteLLM stack running):
    WITH_LLM=1 python examples/us4_rest_caller_example.py

The LLM receives a task and a function definition for rest_caller.
If it decides to call an API, the tool executes and the result is fed back.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from agent.tools.rest_caller import RestCallerTool, RestCallerToolError, format_rest_caller_response


async def _run_tool_only() -> int:
    url = os.getenv("REST_URL", "http://localhost:8000/health")
    method = os.getenv("REST_METHOD", "GET")
    timeout_seconds = float(os.getenv("REST_TIMEOUT_SECONDS", "10"))
    max_body_bytes = int(os.getenv("REST_MAX_BODY_BYTES", "4096"))

    print(f"[tool-only] calling {method.upper()} {url}\n")
    tool = RestCallerTool(timeout_seconds=timeout_seconds, max_body_bytes=max_body_bytes)
    try:
        response = await tool.call(url=url, method=method)
    except RestCallerToolError as exc:
        print(f"rest call failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await tool.aclose()

    print(format_rest_caller_response(response))
    return 0


async def _run_with_llm() -> int:
    litellm_base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1")
    litellm_api_key = os.getenv("LITELLM_API_KEY", "")
    task = os.getenv(
        "REST_TASK",
        "Call GET http://localhost:8000/health and summarize whether dependencies are healthy.",
    )
    timeout_seconds = float(os.getenv("REST_TIMEOUT_SECONDS", "10"))

    if not litellm_api_key:
        print("Set LITELLM_API_KEY before running with WITH_LLM=1.", file=sys.stderr)
        return 1

    from agent.llm import LiteLLMClient

    llm = LiteLLMClient(base_url=litellm_base_url, api_key=litellm_api_key)
    tool = RestCallerTool(timeout_seconds=timeout_seconds)

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
                "When current API data is required, use the rest_caller tool. "
                "Always answer in English."
            ),
        },
        {"role": "user", "content": task},
    ]

    print(f"[with-llm] task: {task!r}")
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
    except RestCallerToolError as exc:
        print(f"rest tool failed: {exc}", file=sys.stderr)
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
