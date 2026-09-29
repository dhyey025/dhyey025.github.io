"""FastAPI application factory and ASGI entry point (``app.main:app``)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import api_router
from app.api.routes.root import router as root_router
from app.core.config import Settings
from app.core.exceptions import InvestorNotFoundError
from app.core.logging import configure_logging
from app.repositories.investor_repository import InvestorRepository

logger = logging.getLogger(__name__)

API_V1_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the (read-only) mandate dataset once at startup; fail fast if it is invalid."""
    settings: Settings = app.state.settings
    app.state.investor_repository = InvestorRepository.from_json_file(settings.investor_data_path)
    logger.info("%s %s started (%s)", settings.app_name, __version__, settings.environment)
    yield
    logger.info("%s shutting down", settings.app_name)


async def _investor_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured FastAPI application."""
    settings = settings or Settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        summary="Agentic Financial Intelligence & Matching Platform - Milestone 1 (deterministic)",
        description=(
            "Independent educational portfolio project using synthetic data. Not affiliated "
            "with, endorsed by, or a product of any financial institution. Not investment advice."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.include_router(root_router)
    app.include_router(api_router, prefix=API_V1_PREFIX)
    app.add_exception_handler(InvestorNotFoundError, _investor_not_found_handler)
    return app


app = create_app()
