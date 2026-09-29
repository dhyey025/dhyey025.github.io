"""Issuer-to-investor matching endpoint."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import MatchingServiceDep
from app.models.issuer import IssuerProfile
from app.models.match import MatchResponse

router = APIRouter(prefix="/matches", tags=["matching"])

DEFAULT_TOP_N = 10
MAX_TOP_N = 50


@router.post(
    "",
    response_model=MatchResponse,
    summary="Rank investor mandates for an issuer",
    description=(
        "Scores every eligible investor mandate against the issuer using the deterministic "
        "matching engine (no LLM) and returns the highest-scoring matches first. Inactive "
        "mandates and mandates whose minimum revenue exceeds the issuer's revenue are excluded."
    ),
)
async def create_matches(
    issuer: IssuerProfile,
    service: MatchingServiceDep,
    top_n: Annotated[
        int, Query(ge=1, le=MAX_TOP_N, description="Maximum number of matches to return.")
    ] = DEFAULT_TOP_N,
) -> MatchResponse:
    return await service.find_matches(issuer, top_n=top_n)
