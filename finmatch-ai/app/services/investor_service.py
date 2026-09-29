"""Investor mandate queries."""

from app.core.exceptions import InvestorNotFoundError
from app.models.investor import InvestorMandate
from app.repositories.investor_repository import InvestorRepository


class InvestorService:
    """Read-side operations over investor mandates."""

    def __init__(self, repository: InvestorRepository) -> None:
        self._repository = repository

    async def list_investors(self, active: bool | None = None) -> list[InvestorMandate]:
        """All mandates, optionally filtered by ``active`` status."""
        mandates = await self._repository.list_all()
        if active is None:
            return list(mandates)
        return [m for m in mandates if m.active is active]

    async def get_investor(self, investor_id: str) -> InvestorMandate:
        """One mandate by ID; raises :class:`InvestorNotFoundError` if absent."""
        mandate = await self._repository.get_by_id(investor_id)
        if mandate is None:
            raise InvestorNotFoundError(investor_id)
        return mandate
