"""Validation rules on the domain models."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.models import CompanyStage, InvestorMandate, InvestorType, IssuerProfile, RiskLevel
from app.models.match import MatchResult
from tests.factories import issuer_payload, make_issuer, make_mandate, mandate_payload


class TestIssuerProfile:
    def test_valid_issuer(self) -> None:
        issuer = make_issuer()
        assert issuer.company_name == "Testfield Systems Ltd"
        assert issuer.company_stage is CompanyStage.GROWTH
        assert issuer.risk_level is RiskLevel.MEDIUM

    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"company_name": ""}, id="empty-company-name"),
            pytest.param({"company_name": "   "}, id="whitespace-company-name"),
            pytest.param({"sector": ""}, id="empty-sector"),
            pytest.param({"sector": "  "}, id="whitespace-sector"),
            pytest.param({"region": ""}, id="empty-region"),
            pytest.param({"id": ""}, id="empty-id"),
            pytest.param({"id": "has spaces"}, id="invalid-id"),
            pytest.param({"deal_size_m": -1}, id="negative-deal-size"),
            pytest.param({"deal_size_m": 0}, id="zero-deal-size"),
            pytest.param({"deal_size_m": 1_000_000}, id="absurd-deal-size"),
            pytest.param({"deal_size_m": float("inf")}, id="infinite-deal-size"),
            pytest.param({"deal_size_m": float("nan")}, id="nan-deal-size"),
            pytest.param({"revenue_m": -0.01}, id="negative-revenue"),
            pytest.param({"risk_level": "extreme"}, id="invalid-risk-level"),
            pytest.param({"risk_level": ""}, id="empty-risk-level"),
            pytest.param({"company_stage": "unicorn"}, id="invalid-stage"),
            pytest.param({"ticker": "BAD TICKER"}, id="invalid-ticker"),
            pytest.param({"unexpected_field": 1}, id="unknown-field"),
        ],
    )
    def test_invalid_issuer_is_rejected(self, overrides: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            IssuerProfile.model_validate(issuer_payload(**overrides))

    @pytest.mark.parametrize(
        "field", ["id", "company_name", "sector", "region", "deal_size_m", "revenue_m"]
    )
    def test_required_fields(self, field: str) -> None:
        payload = issuer_payload()
        del payload[field]
        with pytest.raises(ValidationError):
            IssuerProfile.model_validate(payload)

    def test_zero_revenue_is_allowed(self) -> None:
        assert make_issuer(revenue_m=0).revenue_m == 0.0

    def test_strings_are_trimmed(self) -> None:
        issuer = make_issuer(company_name="  Acme Ltd  ", sector=" Technology ")
        assert issuer.company_name == "Acme Ltd"
        assert issuer.sector == "Technology"

    def test_enums_are_case_insensitive(self) -> None:
        issuer = make_issuer(company_stage=" LATE ", risk_level="High")
        assert issuer.company_stage is CompanyStage.LATE
        assert issuer.risk_level is RiskLevel.HIGH

    def test_ticker_is_normalised(self) -> None:
        assert make_issuer(ticker=" abc.l ").ticker == "ABC.L"
        assert make_issuer(ticker="").ticker is None
        assert make_issuer(ticker=None).ticker is None

    def test_issuer_is_immutable(self) -> None:
        issuer = make_issuer()
        with pytest.raises(ValidationError):
            issuer.deal_size_m = 1.0  # type: ignore[misc]


class TestInvestorMandate:
    def test_valid_mandate(self) -> None:
        mandate = make_mandate(investor_type="pension fund")
        assert mandate.investor_type is InvestorType.PENSION_FUND

    def test_equal_min_and_max_deal_size_is_allowed(self) -> None:
        assert make_mandate(min_deal_size_m=50, max_deal_size_m=50).max_deal_size_m == 50

    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"min_deal_size_m": 200, "max_deal_size_m": 100}, id="min-above-max"),
            pytest.param({"min_deal_size_m": -1}, id="negative-min-deal"),
            pytest.param({"max_deal_size_m": 0}, id="zero-max-deal"),
            pytest.param({"min_revenue_m": -5}, id="negative-min-revenue"),
            pytest.param({"preferred_sectors": []}, id="no-sectors"),
            pytest.param({"preferred_sectors": [""]}, id="empty-sector"),
            pytest.param({"preferred_regions": []}, id="no-regions"),
            pytest.param({"preferred_stages": []}, id="no-stages"),
            pytest.param({"preferred_stages": ["unicorn"]}, id="invalid-stage"),
            pytest.param({"risk_tolerance": "reckless"}, id="invalid-risk"),
            pytest.param({"investor_type": "Hedge Fund"}, id="unknown-investor-type"),
            pytest.param({"investor_name": " "}, id="blank-name"),
        ],
    )
    def test_invalid_mandate_is_rejected(self, overrides: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            InvestorMandate.model_validate(mandate_payload(**overrides))

    def test_active_flag_is_required(self) -> None:
        """A mandate must never become recommendable by omission of ``active``."""
        payload = mandate_payload()
        del payload["active"]
        with pytest.raises(ValidationError):
            InvestorMandate.model_validate(payload)


class TestMatchResultInvariants:
    @staticmethod
    def _payload(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "investor_id": "INV-1",
            "investor_name": "Fund",
            "investor_type": "Pension Fund",
            "total_score": 80.0,
            "sector_score": 30.0,
            "region_score": 20.0,
            "deal_size_score": 20.0,
            "stage_score": 7.5,
            "risk_score": 2.5,
            "matched_criteria": [],
            "partially_matched_criteria": [],
            "unmatched_criteria": [],
            "explanation": "x",
        }
        payload.update(overrides)
        return payload

    def test_consistent_result_is_valid(self) -> None:
        assert MatchResult.model_validate(self._payload()).total_score == 80.0

    def test_total_must_equal_sum_of_components(self) -> None:
        with pytest.raises(ValidationError, match="does not equal sum of components"):
            MatchResult.model_validate(self._payload(total_score=81.0))

    def test_total_cannot_exceed_100(self) -> None:
        with pytest.raises(ValidationError):
            MatchResult.model_validate(
                self._payload(total_score=110.0, risk_score=32.5)  # components sum to 110
            )

    def test_scores_cannot_be_negative(self) -> None:
        with pytest.raises(ValidationError):
            MatchResult.model_validate(self._payload(total_score=70.0, risk_score=-7.5))
