from __future__ import annotations

import httpx
import pytest

from agent.tools.web_search import WebSearchTool, WebSearchToolError, format_search_results


@pytest.mark.asyncio
async def test_web_search_parses_abstract_and_related_topics() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "python"
        return httpx.Response(
            200,
            json={
                "Heading": "Python",
                "AbstractText": "Python is a programming language.",
                "AbstractURL": "https://www.python.org/",
                "RelatedTopics": [
                    {
                        "Text": "PyPI - The Python package index",
                        "FirstURL": "https://pypi.org/",
                    },
                    {
                        "Name": "Tutorials",
                        "Topics": [
                            {
                                "Text": "Python Tutorial - Official tutorial",
                                "FirstURL": "https://docs.python.org/3/tutorial/",
                            }
                        ],
                    },
                ],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = WebSearchTool(client=client)

    response = await tool.search(query="python", max_results=3)

    assert response.provider == "duckduckgo"
    assert response.query == "python"
    assert len(response.results) == 3
    assert response.results[0].title == "Python"
    assert response.results[1].url == "https://pypi.org/"
    assert response.results[2].title == "Python Tutorial"
    assert "Search results for 'python'" in format_search_results(response)

    await client.aclose()


@pytest.mark.asyncio
async def test_web_search_wraps_transport_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = WebSearchTool(client=client)

    with pytest.raises(WebSearchToolError, match="timed out"):
        await tool.search(query="python")

    await client.aclose()


@pytest.mark.asyncio
async def test_web_search_rejects_blank_queries() -> None:
    tool = WebSearchTool(client=httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200))))

    with pytest.raises(WebSearchToolError, match="blank"):
        await tool.search(query="   ")

    await tool.aclose()