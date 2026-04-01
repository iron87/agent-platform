"""LiteLLM client wrapper for alias-based model routing and provider fallback.

This module provides a lightweight async OpenAI-compatible client that routes
all LLM calls through the LiteLLM proxy gateway. Model names are restricted to
three pre-configured aliases:
  - 'default': Primary LLM for reasoning tasks
  - 'fast': Lower-latency chat fallback and short-form tasks
  - 'embedding': Embedding model for semantic memory

The LiteLLM proxy handles provider routing and automatic fallback, making the
agent code cloud-agnostic.
"""

from collections.abc import Mapping
from typing import Any

from openai import AsyncOpenAI
import structlog

logger = structlog.get_logger(__name__)

# Valid aliases that agents are permitted to use
VALID_ALIASES = {"default", "fast", "embedding"}
_TRACE_ONLY_KWARGS = {"trace_callbacks", "trace_context"}


class LiteLLMClientError(Exception):
    """Raised when LiteLLM-specific constraints are violated."""

    pass


def _header_get(headers: Mapping[str, Any] | Any | None, key: str) -> str | None:
    """Fetch a response header case-insensitively from mapping-like objects."""
    if headers is None:
        return None

    getter = getattr(headers, "get", None)
    if callable(getter):
        value = getter(key)
        if value is not None:
            return str(value)
        value = getter(key.lower())
        if value is not None:
            return str(value)

    items = getattr(headers, "items", None)
    if callable(items):
        for header_name, header_value in items():
            if str(header_name).lower() == key.lower():
                return str(header_value)

    return None


def _emit_custom_trace_event(callbacks: list[Any] | None, *, name: str, data: dict[str, Any]) -> None:
    """Emit a custom trace event without allowing tracing failures to break execution."""
    for callback in callbacks or []:
        on_custom_event = getattr(callback, "on_custom_event", None)
        if callable(on_custom_event):
            try:
                on_custom_event(name=name, data=data)
            except TypeError:
                on_custom_event(name, data)
            except Exception:
                logger.debug(
                    "litellm_trace_callback_failed",
                    callback_type=type(callback).__name__,
                    event_name=name,
                )


def _build_fallback_payload(
    *,
    requested_alias: str,
    response: Any,
    raw_response: Any | None,
    trace_context: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Build a structured fallback payload from LiteLLM response metadata."""
    headers = getattr(raw_response, "headers", None)
    response_model = str(getattr(response, "model", "") or "")

    fallback_from = _header_get(headers, "x-litellm-fallback-from")
    fallback_to = _header_get(headers, "x-litellm-fallback-to")
    reason = _header_get(headers, "x-litellm-fallback-reason")
    provider_model = _header_get(headers, "x-litellm-model-id")

    if not fallback_to and response_model in VALID_ALIASES and response_model != requested_alias:
        fallback_to = response_model

    if not fallback_from and fallback_to and fallback_to != requested_alias:
        fallback_from = requested_alias

    if not any((fallback_from, fallback_to, reason)):
        return None

    payload: dict[str, Any] = {
        "requested_alias": requested_alias,
        "fallback_from": fallback_from or requested_alias,
        "fallback_to": fallback_to or response_model or requested_alias,
        "reason": reason or "provider_fallback",
        "provider_model": provider_model,
    }

    for key, value in (trace_context or {}).items():
        if value is not None:
            payload[str(key)] = value

    return payload


class LiteLLMClient:
    """Thin wrapper around AsyncOpenAI for LiteLLM gateway routing.

    Features:
    - Alias-only model calls (no provider strings in agent code)
    - Automatic provider fallback via LiteLLM config
    - Structured warning logs and trace events for fallback routing
    - Trace-only kwargs are stripped before sending requests to the OpenAI SDK

    Usage:
        client = LiteLLMClient(
            base_url="http://litellm:4000/v1",
            api_key=settings.LITELLM_API_KEY
        )
        response = await client.create_completion(
            model="default",  # Must be 'default', 'fast', or 'embedding'
            messages=[...],
        )
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
    ) -> None:
        """Initialize LiteLLM client.

        Args:
            base_url: LiteLLM proxy URL (e.g., "http://litellm:4000/v1")
            api_key: API key for LiteLLM proxy auth (can be dummy for local testing)

        Raises:
            ValueError: If base_url is empty or malformed
        """
        if not base_url:
            raise ValueError("base_url cannot be empty")

        self.base_url = base_url
        self.api_key = api_key
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )

        logger.info(
            "litellm_client_initialized",
            base_url=base_url,
            aliases=list(VALID_ALIASES),
        )

    async def create_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> Any:
        """Create a chat completion using an alias-based model.

        Args:
            model: Alias string ('default', 'fast', or 'embedding')
            messages: List of chat messages (role: "user"|"assistant", content: str)
            **kwargs: Additional parameters to pass to OpenAI API
                (e.g., temperature, max_tokens, top_p)

        Returns:
            OpenAI ChatCompletion response object

        Raises:
            LiteLLMClientError: If model is not a valid alias
            Exception: If LiteLLM is unreachable (propagates from AsyncOpenAI)
        """
        if model not in VALID_ALIASES:
            raise LiteLLMClientError(
                f"model='{model}' is not a valid alias. "
                f"Must be one of {VALID_ALIASES}"
            )

        logger.debug(
            "litellm_completion_request",
            model=model,
            message_count=len(messages),
        )

        request_kwargs = dict(kwargs)
        trace_callbacks = list(request_kwargs.pop("trace_callbacks", []) or [])
        trace_context = dict(request_kwargs.pop("trace_context", {}) or {})
        raw_response: Any | None = None

        try:
            raw_completion_client = getattr(self._client.chat.completions, "with_raw_response", None)
            raw_create = getattr(raw_completion_client, "create", None)

            if callable(raw_create):
                raw_response = await raw_create(
                    model=model,
                    messages=messages,
                    **request_kwargs,
                )
                parser = getattr(raw_response, "parse", None)
                response = parser() if callable(parser) else raw_response
            else:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    **request_kwargs,
                )

            payload = _build_fallback_payload(
                requested_alias=model,
                response=response,
                raw_response=raw_response,
                trace_context=trace_context,
            )
            if payload is not None:
                logger.warning("litellm_provider_fallback", **payload)
                _emit_custom_trace_event(trace_callbacks, name="llm_fallback", data=payload)

            choice = response.choices[0] if getattr(response, "choices", None) else None
            logger.debug(
                "litellm_completion_success",
                model=model,
                response_model=getattr(response, "model", None),
                finish_reason=getattr(choice, "finish_reason", None),
            )
            return response
        except Exception as e:
            logger.error(
                "litellm_completion_failed",
                model=model,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    async def create_embedding(
        self,
        model: str,
        input: str | list[str],
        **kwargs: Any,
    ) -> Any:
        """Create an embedding vector using the embedding alias.

        Args:
            model: Must be 'embedding' alias
            input: Text string or list of text strings to embed
            **kwargs: Additional parameters to pass to OpenAI API

        Returns:
            OpenAI Embedding response object with 'data' list of vectors

        Raises:
            LiteLLMClientError: If model is not 'embedding'
        """
        if model != "embedding":
            raise LiteLLMClientError(
                f"model='{model}' is not the embedding alias. "
                f"Use model='embedding' for embedding requests"
            )

        logger.debug(
            "litellm_embedding_request",
            input_type=type(input).__name__,
            input_count=len(input) if isinstance(input, list) else 1,
        )

        request_kwargs = {key: value for key, value in kwargs.items() if key not in _TRACE_ONLY_KWARGS}

        try:
            response = await self._client.embeddings.create(
                model=model,
                input=input,
                **request_kwargs,
            )
            logger.debug("litellm_embedding_success", model=model)
            return response
        except Exception as e:
            logger.error(
                "litellm_embedding_failed",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    @staticmethod
    def validate_model_alias(model: str) -> bool:
        """Check if a model string is a valid alias.

        Args:
            model: Model name to validate

        Returns:
            True if model is in VALID_ALIASES, False otherwise
        """
        return model in VALID_ALIASES


__all__ = [
    "LiteLLMClient",
    "LiteLLMClientError",
    "VALID_ALIASES",
]
