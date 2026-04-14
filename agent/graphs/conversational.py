"""Conversational graph with session-context-aware message construction."""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any
import structlog

from langgraph.graph import END, START, StateGraph

from agent.graphs.state import AgentState
from agent.llm import VALID_ALIASES
from agent.memory import MemoryScope

logger = structlog.get_logger(__name__)

_TRIVIAL_INPUTS = {
    "hi",
    "hello",
    "hey",
    "ok",
    "thanks",
    "thank you",
    "ciao",
}

_MEMORY_CUES = (
    "remember",
    "preference",
    "prefer",
    "always",
    "never",
    "important",
    "requirement",
    "policy",
    "setup",
    "configuration",
    "for future",
)


def _should_upsert_semantic_memory(user_input: str, output: str) -> tuple[bool, str]:
    text = (user_input or "").strip()
    if not text:
        return False, "empty_input"

    lowered = text.lower()

    # Keep file ingestion turns persisted.
    if lowered.startswith("source file:"):
        return True, "source_file_ingestion"

    # Skip tiny or social-only turns.
    if len(lowered) < 25 or lowered in _TRIVIAL_INPUTS:
        return False, "trivial_or_too_short"

    if any(cue in lowered for cue in _MEMORY_CUES):
        return True, "memory_cue"

    # Persist structured/long facts but avoid embedding every short exchange.
    if "\n" in text or ":" in text or len(text) >= 140:
        return True, "structured_or_long_input"

    assistant_text = (output or "").strip()
    if len(assistant_text) >= 220:
        return True, "long_assistant_output"

    return False, "not_memorable_enough"


async def _upsert_memory_fact_async(
    *,
    memory_store: Any,
    memory_scope: MemoryScope,
    user_input: str,
    output: str,
    session_id: str | None,
    agent_id: str | None,
) -> None:
    try:
        await memory_store.upsert_fact(
            scope=memory_scope,
            text=f"User: {user_input}\nAssistant: {output}",
            metadata={
                "source": "conversational_graph",
                "session_id": session_id,
                "agent_id": agent_id,
            },
        )
    except Exception as exc:
        logger.warning(
            "semantic_memory_upsert_failed",
            tenant_id=memory_scope.tenant_id,
            session_id=memory_scope.user_id,
            error=str(exc),
        )


def _log_memory_task_result(task: asyncio.Task[None], *, tenant_id: str, session_id: str | None) -> None:
    if task.cancelled():
        logger.warning(
            "semantic_memory_upsert_cancelled",
            tenant_id=tenant_id,
            session_id=session_id,
        )
        return

    exc = task.exception()
    if exc is not None:
        logger.warning(
            "semantic_memory_upsert_failed",
            tenant_id=tenant_id,
            session_id=session_id,
            error=str(exc),
        )


def _normalize_messages(messages: list[Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for msg in messages:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            normalized.append({"role": str(msg["role"]), "content": str(msg["content"])})
    return normalized


def _resolve_model_alias(state: AgentState) -> str:
    requested_alias = str(state.get("_model_alias") or "default").strip()
    return requested_alias if requested_alias in VALID_ALIASES else "default"


async def _generate_response(state: AgentState) -> dict[str, Any]:
    turn_start = perf_counter()
    llm_client = state.get("_llm_client")
    memory_store = state.get("_memory_store")
    model_alias = _resolve_model_alias(state)
    system_prompt = str(state.get("_system_prompt") or "")
    callbacks = list(state.get("_trace_callbacks") or [])
    agent_definition = dict(state.get("_agent_definition") or {})
    semantic_memory_enabled = bool(agent_definition.get("semantic_memory_enabled"))

    messages = _normalize_messages(state.get("messages", []))
    memory_scope = MemoryScope(
        tenant_id=str(state.get("tenant_id") or ""),
        user_id=str(state.get("tenant_id") or ""),
        agent_id=str(agent_definition.get("id") or "") or None,
        run_id=str(state.get("job_id") or "") or None,
    )

    # Retrieve relevant semantic memory and inject it into the system context.
    if semantic_memory_enabled and memory_store is not None and memory_scope.tenant_id:
        retrieval_start = perf_counter()
        try:
            records = await memory_store.search(
                scope=memory_scope,
                query=state["input"],
                limit=5,
            )
            retrieval_ms = (perf_counter() - retrieval_start) * 1000
            logger.info(
                "semantic_memory_retrieval_timing",
                tenant_id=memory_scope.tenant_id,
                session_id=memory_scope.user_id,
                duration_ms=round(retrieval_ms, 2),
                result_count=len(records),
                query_chars=len(str(state.get("input") or "")),
            )
            if records:
                memory_lines = [f"- {record.text}" for record in records if record.text]
                if memory_lines:
                    memory_block = "Relevant semantic memory:\n" + "\n".join(memory_lines)
                    system_prompt = (
                        f"{system_prompt}\n\n{memory_block}" if system_prompt else memory_block
                    )
        except Exception as exc:
            retrieval_ms = (perf_counter() - retrieval_start) * 1000
            logger.warning(
                "semantic_memory_retrieval_failed",
                tenant_id=memory_scope.tenant_id,
                session_id=memory_scope.user_id,
                duration_ms=round(retrieval_ms, 2),
                error=str(exc),
            )

    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}, *messages]
    messages.append({"role": "user", "content": state["input"]})

    if llm_client is None:
        # Fail-open fallback for tests or minimal environments.
        output = f"Echo: {state['input']}"
        logger.info(
            "llm_completion_timing",
            tenant_id=state.get("tenant_id"),
            session_id=state.get("session_id"),
            duration_ms=0.0,
            model_alias=model_alias,
            llm_mode="echo_fallback",
        )
    else:
        llm_start = perf_counter()
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
        llm_ms = (perf_counter() - llm_start) * 1000
        logger.info(
            "llm_completion_timing",
            tenant_id=state.get("tenant_id"),
            session_id=state.get("session_id"),
            duration_ms=round(llm_ms, 2),
            model_alias=model_alias,
            llm_mode="remote",
        )
        output = completion.choices[0].message.content or ""

    # Upsert the latest user/assistant exchange in background so response latency
    # is not gated by embedding + vector write time.
    should_upsert, upsert_reason = _should_upsert_semantic_memory(str(state.get("input") or ""), output)
    if (
        semantic_memory_enabled
        and memory_store is not None
        and memory_scope.tenant_id
        and should_upsert
    ):
        upsert_enqueue_start = perf_counter()
        task = asyncio.create_task(
            _upsert_memory_fact_async(
                memory_store=memory_store,
                memory_scope=memory_scope,
                user_input=state["input"],
                output=output,
                session_id=str(state.get("session_id") or "") or None,
                agent_id=str(agent_definition.get("id") or "") or None,
            )
        )
        upsert_enqueue_ms = (perf_counter() - upsert_enqueue_start) * 1000
        logger.info(
            "semantic_memory_upsert_enqueued",
            tenant_id=memory_scope.tenant_id,
            session_id=str(state.get("session_id") or "") or None,
            duration_ms=round(upsert_enqueue_ms, 2),
            reason=upsert_reason,
        )
        task.add_done_callback(
            lambda t: _log_memory_task_result(
                t,
                tenant_id=memory_scope.tenant_id,
                session_id=str(state.get("session_id") or "") or None,
            )
        )
    elif semantic_memory_enabled and memory_store is not None and memory_scope.tenant_id:
        logger.info(
            "semantic_memory_upsert_skipped",
            tenant_id=memory_scope.tenant_id,
            session_id=str(state.get("session_id") or "") or None,
            reason=upsert_reason,
        )

    total_ms = (perf_counter() - turn_start) * 1000
    logger.info(
        "conversational_turn_timing",
        tenant_id=state.get("tenant_id"),
        session_id=state.get("session_id"),
        duration_ms=round(total_ms, 2),
        semantic_memory_enabled=semantic_memory_enabled,
    )

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
