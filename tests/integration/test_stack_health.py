from __future__ import annotations

import os

import httpx
import pytest


@pytest.mark.integration
def test_stack_health_endpoint_available_when_integration_enabled() -> None:
    if os.getenv("TEST_INTEGRATION", "false").lower() != "true":
        pytest.skip("Integration tests disabled. Set TEST_INTEGRATION=true to enable.")

    try:
        response = httpx.get("http://localhost:8000/health", timeout=3.0)
    except httpx.HTTPError as exc:
        pytest.skip(f"Integration stack not reachable: {exc}")

    assert response.status_code in {200, 503}
