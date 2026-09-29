"""Read-only investor mandate repository backed by a JSON file.

Methods are ``async`` so the service layer will not need to change when this is
replaced by a database-backed repository in a later milestone.
"""

import logging
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, ValidationError

from app.core.exceptions import DataIntegrityError
from app.models.investor import InvestorMandate

logger = logging.getLogger(__name__)


class _MandateDataset(BaseModel):
    """On-disk file format: provenance metadata plus the list of mandates."""

    model_config = ConfigDict(extra="forbid")

    metadata: dict[str, Any]
    mandates: list[InvestorMandate]


class InvestorRepository:
    """Immutable, in-memory collection of investor mandates."""

    def __init__(self, mandates: Iterable[InvestorMandate]) -> None:
        ordered = tuple(mandates)
        by_id: dict[str, InvestorMandate] = {}
        for mandate in ordered:
            if mandate.id in by_id:
                raise DataIntegrityError(f"Duplicate investor mandate id: {mandate.id!r}")
            by_id[mandate.id] = mandate
        self._mandates = ordered
        self._by_id: Mapping[str, InvestorMandate] = MappingProxyType(by_id)

    @classmethod
    def from_json_file(cls, path: Path) -> Self:
        """Load and validate mandates from ``path``; fail fast on any invalid record."""
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise DataIntegrityError(
                f"Investor data file not found: {path} (resolved to {path.resolve()})"
            ) from exc
        try:
            dataset = _MandateDataset.model_validate_json(raw)
        except ValidationError as exc:
            raise DataIntegrityError(f"Invalid investor data in {path}: {exc}") from exc

        repository = cls(dataset.mandates)
        logger.info("Loaded %d investor mandates from %s", len(repository), path)
        return repository

    def __len__(self) -> int:
        return len(self._mandates)

    async def list_all(self) -> tuple[InvestorMandate, ...]:
        """All mandates (active and inactive) in file order."""
        return self._mandates

    async def get_by_id(self, investor_id: str) -> InvestorMandate | None:
        """The mandate with this exact ID, or ``None``."""
        return self._by_id.get(investor_id)
