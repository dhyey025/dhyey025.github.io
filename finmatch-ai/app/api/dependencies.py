"""FastAPI dependency providers.

Shared objects live on ``app.state`` (set up in the lifespan handler) rather than in
module-level globals, so each app instance - including those built in tests - owns
its own configuration and data.
"""

from typing import Annotated, cast

from fastapi import Depends, Request

from app.core.config import Settings
from app.repositories.investor_repository import InvestorRepository
from app.services.investor_service import InvestorService
from app.services.matching_service import MatchingService


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_investor_repository(request: Request) -> InvestorRepository:
    return cast(InvestorRepository, request.app.state.investor_repository)


def get_investor_service(
    repository: Annotated[InvestorRepository, Depends(get_investor_repository)],
) -> InvestorService:
    return InvestorService(repository)


def get_matching_service(
    repository: Annotated[InvestorRepository, Depends(get_investor_repository)],
) -> MatchingService:
    return MatchingService(repository)


SettingsDep = Annotated[Settings, Depends(get_settings)]
InvestorServiceDep = Annotated[InvestorService, Depends(get_investor_service)]
MatchingServiceDep = Annotated[MatchingService, Depends(get_matching_service)]
