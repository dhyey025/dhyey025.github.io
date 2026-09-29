"""Liveness endpoint."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.dependencies import SettingsDep

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["healthy"]
    service: str


@router.get("/health", response_model=HealthResponse, summary="Service health check")
async def health(settings: SettingsDep) -> HealthResponse:
    # Startup fails if the mandate dataset cannot be loaded, so a responding
    # process is a healthy one in Milestone 1.
    return HealthResponse(status="healthy", service=settings.service_name)
