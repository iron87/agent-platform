from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.config import Settings, get_settings
from api.db import create_engine, create_session_factory
from api.logging import configure_logging, get_logger
from api.routes.agents import router as agents_router
from api.routes.approvals import router as approvals_router
from api.routes.health import router as health_router
from api.routes.jobs import router as jobs_router

logger = get_logger(__name__)


def run_startup_checks(settings: Settings) -> None:
    if not settings.API_PREFIX.startswith("/"):
        raise RuntimeError("API_PREFIX must start with '/'.")

    create_engine(settings)
    create_session_factory(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    run_startup_checks(settings)
    app.state.settings = settings
    app.state.session_factory = create_session_factory(settings)
    logger.info("application_startup_complete", env=settings.ENV)
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()

    app = FastAPI(
        title="2brain Agent API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.settings = runtime_settings
    app.include_router(health_router)
    app.include_router(agents_router, prefix=runtime_settings.API_PREFIX)
    app.include_router(jobs_router, prefix=runtime_settings.API_PREFIX)
    app.include_router(approvals_router, prefix=runtime_settings.API_PREFIX)
    return app


app = create_app()
