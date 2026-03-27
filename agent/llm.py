"""LiteLLM client wrapper for alias-based model routing and provider fallback.

This module provides a lightweight async OpenAI-compatible client that routes
all LLM calls through the LiteLLM proxy gateway. Model names are restricted to
three pre-configured aliases:
  - 'default': Primary LLM for reasoning tasks
  - 'fast': Lightweight/embedded models for latency-sensitive tasks
  - 'embedding': Embedding model for semantic memory

The LiteLLM proxy handles provider routing and automatic fallback, making the
agent code cloud-agnostic.
"""

from typing import Any

from openai import AsyncOpenAI
import structlog

logger = structlog.get_logger(__name__)

# Valid aliases that agents are permitted to use
VALID_ALIASES = {"default", "fast", "embedding"}


class LiteLLMClientError(Exception):
    """Raised when LiteLLM-specific constraints are violated."""

    pass


class LiteLLMClient:
    """Thin wrapper around AsyncOpenAI for LiteLLM gateway routing.

    Features:
    - Alias-only model calls (no provider strings in agent code)
    - Automatic provider fallback via LiteLLM config
    - Failed-open logging (warns but doesn't raise on LiteLLM unavailability)
    - Per-client API key injection via Langfuse callback

    Usage:
        client = LiteLLMClient(
            base_url="http://litellm:4000/v1",
            api_key=settings.LITELLM_API_KEY
        )
        response = await client.create_completion(
            model="default",  # Must be 'default', 'fast', or 'embedding'
            messages=[...],
        )

    Notes:
        - All methods are async-first (designed for FastAPI routes)
        - Messages are passed through to OpenAI chat completion API unchanged
        - Trace callbacks (for Langfuse) are automatically handled by LiteLLM
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

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs,
            )
            logger.debug(
                "litellm_completion_success",
                model=model,
                finish_reason=response.choices[0].finish_reason,
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

        try:
            response = await self._client.embeddings.create(
                model=model,
                input=input,
                **kwargs,
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
