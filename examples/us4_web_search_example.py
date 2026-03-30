#!/usr/bin/env python3
"""US4 example: web-search tool, with two runnable modes.

MODE 1 — tool only (default, no LLM required):
    python examples/us4_web_search_example.py
    WEB_SEARCH_QUERY="LangGraph" python examples/us4_web_search_example.py

    Calls WebSearchTool.search() directly and prints formatted results.
    No LiteLLM or API key needed.

MODE 2 — full LLM + tool loop (requires LiteLLM stack running):
    WITH_LLM=1 python examples/us4_web_search_example.py

    The LLM receives the user question and a function definition for web_search.
    If it decides to call the tool, the tool executes and the result is fed back.
    The LLM then returns a synthesised answer.
    Requires LITELLM_BASE_URL and LITELLM_API_KEY in the environment (or .env).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from agent.tools.web_search import WebSearchTool, WebSearchToolError, format_search_results


# ── Mode 1: tool only ──────────────────────────────────────────────────────────

async def _run_tool_only() -> int:
    query = os.getenv("WEB_SEARCH_QUERY", "latest LangGraph release notes")
    max_results = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
    timeout_seconds = float(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "10"))

    print(f"[tool-only] searching: {query!r}\n")
    tool = WebSearchTool(timeout_seconds=timeout_seconds, max_results=max_results)
    try:
        response = await tool.search(query=query, max_results=max_results)
    except WebSearchToolError as exc:
        print(f"web search failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await tool.aclose()

    print(format_search_results(response))
    return 0


# ── Mode 2: LLM decides → tool executes → LLM synthesises ─────────────────────

async def _run_with_llm() -> int:
    litellm_base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1")
    litellm_api_key = os.getenv("LITELLM_API_KEY", "")
    question = os.getenv("WEB_SEARCH_QUERY", "What is LangGraph and when was it last updated?")
    max_results = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "3"))

    if not litellm_api_key:
        print("Set LITELLM_API_KEY before running with WITH_LLM=1.", file=sys.stderr)
        return 1

    from agent.llm import LiteLLMClient

    llm = LiteLLMClient(base_url=litellm_base_url, api_key=litellm_api_key)
    tool = WebSearchTool(max_results=max_results)

    # ── Step 1: send question + tool definition to the LLM ────────────────────
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
                "You are a helpful assistant. "
                "When you need current information, use the web_search tool. "
                "Always answer in English."
            ),
        },
        {"role": "user", "content": question},
    ]

    print(f"[with-llm] question: {question!r}")
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
        # LLM answered directly without calling the tool
        print("[with-llm] LLM answered without tool call:")
        print(choice.message.content or "")
        await tool.aclose()
        return 0

    # ── Step 2: execute the tool the LLM requested ────────────────────────────
    tool_call = choice.message.tool_calls[0]
    args = json.loads(tool_call.function.arguments)
    print(f"[with-llm] step 2 — LLM called tool '{tool_call.function.name}' with args: {args}")

    try:
        search_result = await tool.arun(**args)
    except WebSearchToolError as exc:
        print(f"tool execution failed: {exc}", file=sys.stderr)
        await tool.aclose()
        return 1
    finally:
        await tool.aclose()

    # ── Step 3: feed tool output back → LLM synthesises final answer ──────────
    messages.append(choice.message.model_dump(exclude_unset=True))
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": tool_call.function.name,
            "content": json.dumps(search_result, default=str),
        }
    )

    print("[with-llm] step 3 — feeding tool result back to LLM ...\n")
    try:
        resp2 = await llm.create_completion(model="fast", messages=messages)
    except Exception as exc:
        print(f"LLM synthesis call failed: {exc}", file=sys.stderr)
        return 1

    print("[with-llm] final answer:")
    print(resp2.choices[0].message.content or "")
    return 0


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> int:
    if os.getenv("WITH_LLM"):
        return asyncio.run(_run_with_llm())
    return asyncio.run(_run_tool_only())


if __name__ == "__main__":
    raise SystemExit(main())