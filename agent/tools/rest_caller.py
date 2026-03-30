from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any

import httpx


DEFAULT_REST_CALLER_TIMEOUT_SECONDS = 10.0
DEFAULT_REST_CALLER_MAX_BODY_BYTES = 16384
ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


class RestCallerToolError(RuntimeError):
    """Raised when the REST caller tool cannot complete a request."""


@dataclass(frozen=True)
class RestCallerResponse:
    method: str
    url: str
    status_code: int
    headers: dict[str, str]
    body: str
    body_truncated: bool
    took_ms: int

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ok"] = 200 <= self.status_code < 300
        return payload


class RestCallerTool:
    name = "rest_caller"
    description = "Call external REST APIs with method, headers, query params, and timeout handling."
    input_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "minLength": 1,
                "description": "Absolute URL to call (http or https).",
            },
            "method": {
                "type": "string",
                "enum": sorted(ALLOWED_METHODS),
                "description": "HTTP method to use.",
            },
            "headers": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "description": "Optional request headers.",
            },
            "params": {
                "type": "object",
                "additionalProperties": {
                    "anyOf": [{"type": "string"}, {"type": "number"}, {"type": "boolean"}],
                },
                "description": "Optional query-string parameters.",
            },
            "json_body": {
                "type": ["object", "array", "string", "number", "boolean", "null"],
                "description": "Optional JSON request body.",
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 0.1,
                "maximum": 120,
                "description": "Optional override timeout for this call.",
            },
        },
        "required": ["url"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_REST_CALLER_TIMEOUT_SECONDS,
        max_body_bytes: int = DEFAULT_REST_CALLER_MAX_BODY_BYTES,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_body_bytes = max_body_bytes
        self._client = client
        self._owns_client = client is None

    @property
    def tool_definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    async def arun(
        self,
        *,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        response = await self.call(
            url=url,
            method=method,
            headers=headers,
            params=params,
            json_body=json_body,
            timeout_seconds=timeout_seconds,
        )
        return response.to_dict()

    async def call(
        self,
        *,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        timeout_seconds: float | None = None,
    ) -> RestCallerResponse:
        normalized_url = url.strip()
        if not normalized_url:
            raise RestCallerToolError("url must not be blank")
        if not (normalized_url.startswith("http://") or normalized_url.startswith("https://")):
            raise RestCallerToolError("url must be absolute and start with http:// or https://")

        normalized_method = method.upper().strip()
        if normalized_method not in ALLOWED_METHODS:
            raise RestCallerToolError(f"unsupported method '{method}'. Allowed methods: {sorted(ALLOWED_METHODS)}")

        effective_timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        client = self._client or self._build_client(timeout_seconds=effective_timeout)
        started = perf_counter()

        try:
            http_response = await client.request(
                method=normalized_method,
                url=normalized_url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=effective_timeout,
            )
        except httpx.TimeoutException as exc:
            raise RestCallerToolError(f"REST call timed out after {effective_timeout}s: {exc}") from exc
        except httpx.HTTPError as exc:
            raise RestCallerToolError(f"REST call failed: {exc}") from exc

        body = self._truncate_text(http_response.text)
        took_ms = int((perf_counter() - started) * 1000)
        response_headers = {k: v for k, v in http_response.headers.items()}
        original_len = len(http_response.text.encode("utf-8", errors="ignore"))

        return RestCallerResponse(
            method=normalized_method,
            url=str(http_response.request.url),
            status_code=http_response.status_code,
            headers=response_headers,
            body=body,
            body_truncated=original_len > self.max_body_bytes,
            took_ms=took_ms,
        )

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_client(self, *, timeout_seconds: float) -> httpx.AsyncClient:
        self._client = httpx.AsyncClient(timeout=timeout_seconds)
        return self._client

    def _truncate_text(self, text: str) -> str:
        encoded = text.encode("utf-8", errors="ignore")
        if len(encoded) <= self.max_body_bytes:
            return text
        return encoded[: self.max_body_bytes].decode("utf-8", errors="ignore")


def build_rest_caller_tool(
    *,
    timeout_seconds: float = DEFAULT_REST_CALLER_TIMEOUT_SECONDS,
    max_body_bytes: int = DEFAULT_REST_CALLER_MAX_BODY_BYTES,
) -> RestCallerTool:
    return RestCallerTool(timeout_seconds=timeout_seconds, max_body_bytes=max_body_bytes)


def format_rest_caller_response(response: RestCallerResponse) -> str:
    lines = [
        f"HTTP {response.status_code} in {response.took_ms}ms",
        f"{response.method} {response.url}",
        "",
        "=== Body ===",
        response.body or "<empty>",
    ]
    return "\n".join(lines)
