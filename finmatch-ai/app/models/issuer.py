"""Issuer (company seeking capital) domain model."""

from pydantic import ConfigDict, Field, field_validator

from app.models.common import (
    MAX_DEAL_SIZE_M,
    MAX_REVENUE_M,
    CompanyStage,
    DomainModel,
    Identifier,
    Label,
    NonEmptyStr,
    RiskLevel,
    Ticker,
)


class IssuerProfile(DomainModel):
    """A company seeking capital. Monetary values are in USD millions."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "ISS-001",
                    "company_name": "Lumenfield Analytics Ltd",
                    "ticker": None,
                    "sector": "Technology",
                    "region": "UK",
                    "deal_size_m": 50,
                    "revenue_m": 30,
                    "company_stage": "growth",
                    "risk_level": "high",
                }
            ]
        }
    )

    id: Identifier
    company_name: NonEmptyStr
    ticker: Ticker | None = None
    sector: Label
    region: Label
    deal_size_m: float = Field(
        gt=0, le=MAX_DEAL_SIZE_M, description="Capital sought, USD millions (> 0)."
    )
    revenue_m: float = Field(
        ge=0, le=MAX_REVENUE_M, description="Annual revenue, USD millions (>= 0)."
    )
    company_stage: CompanyStage
    risk_level: RiskLevel

    @field_validator("ticker", mode="before")
    @classmethod
    def _normalise_ticker(cls, value: object) -> object:
        """Upper-case tickers; treat a blank ticker as "no ticker" (e.g. a private company)."""
        if isinstance(value, str):
            value = value.strip().upper()
            return value or None
        return value
