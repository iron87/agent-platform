from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any

import httpx


DEFAULT_WEB_SEARCH_BASE_URL = "https://api.duckduckgo.com/"
DEFAULT_WEB_SEARCH_TIMEOUT_SECONDS = 10.0
DEFAULT_WEB_SEARCH_MAX_RESULTS = 5


class WebSearchToolError(RuntimeError):
    """Raised when the web-search tool cannot complete a request."""


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = "duckduckgo"


@dataclass(frozen=True)
class WebSearchResponse:
    query: str
    provider: str
    results: list[SearchResult]
    took_ms: int

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["result_count"] = len(self.results)
        return payload


class WebSearchTool:
    name = "web_search"
    description = "Search the public web and return a concise list of relevant results."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 1,
                "description": "Natural-language query to search for.",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "Maximum number of search results to return.",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_WEB_SEARCH_BASE_URL,
        timeout_seconds: float = DEFAULT_WEB_SEARCH_TIMEOUT_SECONDS,
        max_results: int = DEFAULT_WEB_SEARCH_MAX_RESULTS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_results = max_results
        self._client = client
        self._owns_client = client is None

    @property
    def tool_definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    async def arun(self, *, query: str, max_results: int | None = None) -> dict[str, Any]:
        response = await self.search(query=query, max_results=max_results)
        return response.to_dict()

    async def search(self, *, query: str, max_results: int | None = None) -> WebSearchResponse:
        normalized_query = query.strip()
        if not normalized_query:
            raise WebSearchToolError("query must not be blank")

        limit = max_results or self.max_results
        limit = max(1, min(limit, 10))
        client = self._client or self._build_client()
        started = perf_counter()

        try:
            response = await client.get(
                self.base_url,
                params={
                    "q": normalized_query,
                    "format": "json",
                    "no_html": "1",
                    "no_redirect": "1",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise WebSearchToolError(f"web search timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise WebSearchToolError(f"web search request failed: {exc}") from exc
        except ValueError as exc:
            raise WebSearchToolError("web search returned invalid JSON") from exc

        results = self._extract_results(payload, limit=limit)
        took_ms = int((perf_counter() - started) * 1000)
        return WebSearchResponse(
            query=normalized_query,
            provider="duckduckgo",
            results=results,
            took_ms=took_ms,
        )

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_client(self) -> httpx.AsyncClient:
        self._client = httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={"User-Agent": "2brain-platform-web-search/1.0"},
        )
        return self._client

    def _extract_results(self, payload: dict[str, Any], *, limit: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        abstract_url = str(payload.get("AbstractURL") or "").strip()
        abstract_text = str(payload.get("AbstractText") or "").strip()
        heading = str(payload.get("Heading") or payload.get("AbstractSource") or "").strip()
        if abstract_url and abstract_text:
            seen_urls.add(abstract_url)
            results.append(
                SearchResult(
                    title=heading or abstract_url,
                    url=abstract_url,
                    snippet=abstract_text,
                )
            )

        for item in payload.get("RelatedTopics", []):
            if len(results) >= limit:
                break
            results.extend(self._flatten_related_topic(item, seen_urls=seen_urls, limit=limit - len(results)))

        return results[:limit]

    def _flatten_related_topic(
        self,
        item: dict[str, Any],
        *,
        seen_urls: set[str],
        limit: int,
    ) -> list[SearchResult]:
        if limit <= 0:
            return []

        if "Topics" in item:
            nested_results: list[SearchResult] = []
            for nested_item in item.get("Topics", []):
                if len(nested_results) >= limit:
                    break
                nested_results.extend(
                    self._flatten_related_topic(
                        nested_item,
                        seen_urls=seen_urls,
                        limit=limit - len(nested_results),
                    )
                )
            return nested_results

        url = str(item.get("FirstURL") or "").strip()
        text = str(item.get("Text") or "").strip()
        if not url or not text or url in seen_urls:
            return []

        title, _, snippet = text.partition(" - ")
        seen_urls.add(url)
        return [
            SearchResult(
                title=title.strip() or url,
                url=url,
                snippet=(snippet or text).strip(),
            )
        ]


def build_web_search_tool(**kwargs: Any) -> WebSearchTool:
    return WebSearchTool(**kwargs)


def format_search_results(response: WebSearchResponse) -> str:
    if not response.results:
        return f"No web results found for '{response.query}'."

    lines = [f"Search results for '{response.query}' ({response.provider}, {response.took_ms} ms):"]
    for index, result in enumerate(response.results, start=1):
        lines.append(f"{index}. {result.title} - {result.url}")
        lines.append(f"   {result.snippet}")
    return "\n".join(lines)


__all__ = [
    "DEFAULT_WEB_SEARCH_BASE_URL",
    "DEFAULT_WEB_SEARCH_MAX_RESULTS",
    "DEFAULT_WEB_SEARCH_TIMEOUT_SECONDS",
    "SearchResult",
    "WebSearchResponse",
    "WebSearchTool",
    "WebSearchToolError",
    "build_web_search_tool",
    "format_search_results",
]