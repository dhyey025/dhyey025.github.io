"""Application information endpoint (``GET /``)."""

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__
from app.api.dependencies import SettingsDep

router = APIRouter(tags=["meta"])

DISCLAIMER = (
    "FinMatch AI is an independent educational portfolio project using synthetic data. "
    "It is not affiliated with, endorsed by, or a product of any financial institution. "
    "Outputs are illustrative and are not investment advice."
)


class AppInfo(BaseModel):
    name: str
    version: str
    description: str
    milestone: str
    docs_url: str
    health_url: str
    disclaimer: str


@router.get("/", response_model=AppInfo, summary="Application information")
async def app_info(settings: SettingsDep) -> AppInfo:
    return AppInfo(
        name=settings.app_name,
        version=__version__,
        description="Agentic Financial Intelligence & Matching Platform",
        milestone="M1 - deterministic matching foundation (no AI/LLM components yet)",
        docs_url="/docs",
        health_url="/api/v1/health",
        disclaimer=DISCLAIMER,
    )
