"""Investor mandate domain model."""

from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.models.common import (
    MAX_DEAL_SIZE_M,
    MAX_REVENUE_M,
    CompanyStage,
    DomainModel,
    Identifier,
    InvestorType,
    Label,
    NonEmptyStr,
    RiskLevel,
)


class InvestorMandate(DomainModel):
    """What an investor is willing to invest in. Monetary values are in USD millions.

    ``active`` is deliberately required (no default) so a mandate can never become
    eligible for recommendations by omission.
    """

    id: Identifier
    investor_name: NonEmptyStr
    investor_type: InvestorType
    preferred_sectors: list[Label] = Field(min_length=1)
    preferred_regions: list[Label] = Field(min_length=1)
    min_deal_size_m: float = Field(ge=0, le=MAX_DEAL_SIZE_M)
    max_deal_size_m: float = Field(gt=0, le=MAX_DEAL_SIZE_M)
    min_revenue_m: float | None = Field(
        default=None,
        ge=0,
        le=MAX_REVENUE_M,
        description="Eligibility threshold on issuer revenue; null means no minimum.",
    )
    preferred_stages: list[CompanyStage] = Field(min_length=1)
    risk_tolerance: RiskLevel
    active: bool

    @model_validator(mode="after")
    def _check_deal_size_range(self) -> Self:
        if self.max_deal_size_m < self.min_deal_size_m:
            raise ValueError("max_deal_size_m must be greater than or equal to min_deal_size_m")
        return self


class InvestorListResponse(BaseModel):
    """Envelope for investor listings (leaves room for pagination later)."""

    count: int = Field(ge=0)
    investors: list[InvestorMandate]
