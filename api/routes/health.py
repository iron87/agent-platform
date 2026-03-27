"""Health check route with dependency probes for postgres, redis, and qdrant."""

from __future__ import annotations

import time
from typing import Any

import asyncpg
import redis.asyncio as aioredis
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/live", include_in_schema=True)
async def live() -> JSONResponse:
    """Liveness probe for container/runtime health.

    This endpoint intentionally does not check external dependencies.
    It returns 200 as long as the API process can serve requests.
    """
    return JSONResponse(content={"status": "alive"}, status_code=200)


async def _probe_postgres(database_url: str) -> dict[str, Any]:
    start = time.monotonic()
    try:
        conn = await asyncpg.connect(database_url, timeout=5)
        await conn.fetchval("SELECT 1")
        await conn.close()
        return {"status": "healthy", "latency_ms": round((time.monotonic() - start) * 1000)}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


async def _probe_redis(redis_url: str) -> dict[str, Any]:
    start = time.monotonic()
    client: aioredis.Redis | None = None
    try:
        client = aioredis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
        await client.ping()
        return {"status": "healthy", "latency_ms": round((time.monotonic() - start) * 1000)}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}
    finally:
        if client:
            await client.aclose()


async def _probe_qdrant(qdrant_url: str) -> dict[str, Any]:
    import httpx

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{qdrant_url.rstrip('/')}/healthz")
            resp.raise_for_status()
        return {"status": "healthy", "latency_ms": round((time.monotonic() - start) * 1000)}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


@router.get("/health", include_in_schema=True)
async def health(request: Request) -> JSONResponse:
    """Return platform health with per-dependency probe results.

    Probes postgres, redis, and qdrant. Overall status is ``ok`` only when all
    three dependencies are healthy. Returns ``503`` if any probe fails.
    """
    settings = request.app.state.settings

    postgres_result = await _probe_postgres(settings.DATABASE_URL)
    redis_result = await _probe_redis(settings.REDIS_URL)
    qdrant_result = await _probe_qdrant(settings.QDRANT_URL)

    all_healthy = all(
        r["status"] == "healthy"
        for r in (postgres_result, redis_result, qdrant_result)
    )

    body = {
        "status": "ok" if all_healthy else "degraded",
        "dependencies": {
            "postgres": postgres_result,
            "redis": redis_result,
            "qdrant": qdrant_result,
        },
    }
    return JSONResponse(content=body, status_code=200 if all_healthy else 503)

