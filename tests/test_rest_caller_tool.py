from __future__ import annotations

import httpx
import pytest

from agent.tools.rest_caller import RestCallerTool, RestCallerToolError, format_rest_caller_response


@pytest.mark.asyncio
async def test_rest_caller_get_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url).startswith("https://api.example.com/test")
        return httpx.Response(200, json={"ok": True, "value": 42})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = RestCallerTool(client=client)

    response = await tool.call(url="https://api.example.com/test", params={"q": "abc"})

    assert response.status_code == 200
    assert "ok" in response.body
    assert response.method == "GET"
    assert "HTTP 200" in format_rest_caller_response(response)

    await client.aclose()


@pytest.mark.asyncio
async def test_rest_caller_post_json_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.headers["x-test"] == "1"
        assert request.content.decode("utf-8") == '{"name":"federico"}'
        return httpx.Response(201, text="created")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = RestCallerTool(client=client)

    response = await tool.call(
        url="https://api.example.com/users",
        method="post",
        headers={"x-test": "1"},
        json_body={"name": "federico"},
    )

    assert response.status_code == 201
    assert response.method == "POST"
    assert response.body == "created"

    await client.aclose()


@pytest.mark.asyncio
async def test_rest_caller_rejects_blank_url() -> None:
    tool = RestCallerTool(client=httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200))))

    with pytest.raises(RestCallerToolError, match="blank"):
        await tool.call(url="   ")

    await tool.aclose()


@pytest.mark.asyncio
async def test_rest_caller_rejects_non_http_url() -> None:
    tool = RestCallerTool(client=httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200))))

    with pytest.raises(RestCallerToolError, match="http:// or https://"):
        await tool.call(url="ftp://example.com")

    await tool.aclose()


@pytest.mark.asyncio
async def test_rest_caller_rejects_unsupported_method() -> None:
    tool = RestCallerTool(client=httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200))))

    with pytest.raises(RestCallerToolError, match="unsupported method"):
        await tool.call(url="https://example.com", method="TRACE")

    await tool.aclose()


@pytest.mark.asyncio
async def test_rest_caller_wraps_timeout_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = RestCallerTool(client=client)

    with pytest.raises(RestCallerToolError, match="timed out"):
        await tool.call(url="https://api.example.com/slow", timeout_seconds=0.1)

    await client.aclose()


@pytest.mark.asyncio
async def test_rest_caller_truncates_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="x" * 200)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = RestCallerTool(client=client, max_body_bytes=20)

    response = await tool.call(url="https://api.example.com/big")

    assert len(response.body.encode("utf-8")) <= 20

    await client.aclose()


@pytest.mark.asyncio
async def test_rest_caller_arun_returns_dict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = RestCallerTool(client=client)

    payload = await tool.arun(url="https://api.example.com/ping")

    assert payload["status_code"] == 200
    assert payload["ok"] is True
    assert payload["method"] == "GET"
    assert "body" in payload
    assert payload["body_truncated"] is False

    await client.aclose()
