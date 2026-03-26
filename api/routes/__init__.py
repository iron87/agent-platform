from api.routes.agents import router as agents_router
from api.routes.approvals import router as approvals_router
from api.routes.health import router as health_router
from api.routes.jobs import router as jobs_router

__all__ = [
    "agents_router",
    "approvals_router",
    "health_router",
    "jobs_router",
]
