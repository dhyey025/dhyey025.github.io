"""Investor mandate endpoints."""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.dependencies import InvestorServiceDep
from app.models.investor import InvestorListResponse, InvestorMandate

router = APIRouter(prefix="/investors", tags=["investors"])


@router.get("", response_model=InvestorListResponse, summary="List synthetic investor mandates")
async def list_investors(
    service: InvestorServiceDep,
    active: Annotated[
        bool | None, Query(description="Filter by active status; omit to return all.")
    ] = None,
) -> InvestorListResponse:
    investors = await service.list_investors(active=active)
    return InvestorListResponse(count=len(investors), investors=investors)


@router.get(
    "/{investor_id}",
    response_model=InvestorMandate,
    summary="Get one investor mandate",
    responses={404: {"description": "Investor mandate not found"}},
)
async def get_investor(
    service: InvestorServiceDep,
    investor_id: Annotated[str, Path(min_length=1, max_length=64)],
) -> InvestorMandate:
    return await service.get_investor(investor_id)
