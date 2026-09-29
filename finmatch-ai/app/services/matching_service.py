"""Matching orchestration: load mandates, run the deterministic engine, apply top_n."""

import logging

from app.models.issuer import IssuerProfile
from app.models.match import MatchResponse
from app.repositories.investor_repository import InvestorRepository
from app.services.matching_engine import SCORING_VERSION, rank_investors

logger = logging.getLogger(__name__)


class MatchingService:
    """Produces ranked, explained investor matches for an issuer.

    All scoring is delegated to :mod:`app.services.matching_engine`; this class only
    fetches data and shapes the response.
    """

    def __init__(self, repository: InvestorRepository) -> None:
        self._repository = repository

    async def find_matches(self, issuer: IssuerProfile, top_n: int) -> MatchResponse:
        """Return the ``top_n`` highest-scoring eligible mandates for ``issuer``."""
        if top_n < 1:
            raise ValueError("top_n must be at least 1")

        mandates = await self._repository.list_all()
        ranked = rank_investors(issuer, mandates)
        logger.info(
            "Matched issuer %s: %d mandates, %d eligible candidates, returning %d",
            issuer.id,
            len(mandates),
            len(ranked),
            min(top_n, len(ranked)),
        )
        return MatchResponse(
            issuer=issuer,
            scoring_version=SCORING_VERSION,
            number_of_candidates=len(ranked),
            matches=ranked[:top_n],
        )
