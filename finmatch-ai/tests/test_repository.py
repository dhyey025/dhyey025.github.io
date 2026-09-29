"""Investor repository and synthetic dataset integrity."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.core.exceptions import DataIntegrityError
from app.models import CompanyStage, InvestorType, RiskLevel
from app.repositories.investor_repository import InvestorRepository
from app.services.matching_engine import normalise_label
from tests.conftest import DATA_PATH
from tests.factories import make_mandate, mandate_payload

WriteDataset = Callable[[list[dict[str, Any]]], Path]


@pytest.fixture(scope="module")
def repository() -> InvestorRepository:
    return InvestorRepository.from_json_file(DATA_PATH)


class TestSyntheticDataset:
    """The committed dataset must be varied enough to exercise every scoring path."""

    async def test_has_at_least_15_mandates_with_unique_ids(
        self, repository: InvestorRepository
    ) -> None:
        mandates = await repository.list_all()
        assert len(mandates) >= 15
        assert len({m.id for m in mandates}) == len(mandates)

    async def test_covers_every_investor_type(self, repository: InvestorRepository) -> None:
        mandates = await repository.list_all()
        assert {m.investor_type for m in mandates} == set(InvestorType)

    async def test_covers_required_sectors_and_regions(
        self, repository: InvestorRepository
    ) -> None:
        mandates = await repository.list_all()
        sectors = {normalise_label(s) for m in mandates for s in m.preferred_sectors}
        regions = {normalise_label(r) for m in mandates for r in m.preferred_regions}
        assert sectors >= {
            "technology",
            "financial services",
            "healthcare",
            "energy",
            "industrial",
            "consumer",
            "infrastructure",
        }
        assert regions >= {"uk", "europe", "north america", "asia pacific", "global"}

    async def test_covers_every_stage_and_risk_tolerance(
        self, repository: InvestorRepository
    ) -> None:
        mandates = await repository.list_all()
        assert {s for m in mandates for s in m.preferred_stages} == set(CompanyStage)
        assert {m.risk_tolerance for m in mandates} == set(RiskLevel)

    async def test_has_active_inactive_and_varied_thresholds(
        self, repository: InvestorRepository
    ) -> None:
        mandates = await repository.list_all()
        assert any(m.active for m in mandates)
        assert any(not m.active for m in mandates)
        assert any(m.min_revenue_m is None for m in mandates)
        assert len({m.min_revenue_m for m in mandates if m.min_revenue_m is not None}) >= 5
        assert len({(m.min_deal_size_m, m.max_deal_size_m) for m in mandates}) >= 10

    def test_dataset_is_labelled_synthetic(self) -> None:
        metadata = json.loads(DATA_PATH.read_text(encoding="utf-8"))["metadata"]
        assert metadata["synthetic"] is True
        assert metadata["currency"] == "USD"
        assert metadata["monetary_unit"] == "millions"


class TestInvestorRepository:
    async def test_get_by_id(self, repository: InvestorRepository) -> None:
        mandate = await repository.get_by_id("INV-001")
        assert mandate is not None
        assert mandate.investor_name == "Aldermoor Pension Trust"

    async def test_get_unknown_id_returns_none(self, repository: InvestorRepository) -> None:
        assert await repository.get_by_id("INV-999") is None

    async def test_preserves_file_order(self, write_dataset: WriteDataset) -> None:
        path = write_dataset([mandate_payload(id="INV-B"), mandate_payload(id="INV-A")])
        mandates = await InvestorRepository.from_json_file(path).list_all()
        assert [m.id for m in mandates] == ["INV-B", "INV-A"]

    def test_duplicate_ids_are_rejected(self) -> None:
        with pytest.raises(DataIntegrityError, match="Duplicate investor mandate id"):
            InvestorRepository([make_mandate(id="INV-X"), make_mandate(id="INV-X")])

    def test_missing_file_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(DataIntegrityError, match="not found"):
            InvestorRepository.from_json_file(tmp_path / "missing.json")

    def test_invalid_record_is_rejected(self, write_dataset: WriteDataset) -> None:
        path = write_dataset([mandate_payload(min_deal_size_m=500, max_deal_size_m=100)])
        with pytest.raises(DataIntegrityError, match="Invalid investor data"):
            InvestorRepository.from_json_file(path)

    def test_malformed_json_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(DataIntegrityError):
            InvestorRepository.from_json_file(path)
