"""Route modules. ``api_router`` is mounted under ``/api/v1``."""

from fastapi import APIRouter

from app.api.routes import health, investors, matches

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(investors.router)
api_router.include_router(matches.router)

__all__ = ["api_router"]
