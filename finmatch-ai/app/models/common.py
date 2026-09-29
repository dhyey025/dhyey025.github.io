"""Shared domain types: controlled vocabularies and constrained string types."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints

# Upper bounds reject obviously invalid input; values are USD millions.
MAX_DEAL_SIZE_M = 100_000.0  # USD 100bn
MAX_REVENUE_M = 1_000_000.0  # USD 1tn


class DomainModel(BaseModel):
    """Base for domain models: immutable, strict about unknown fields, finite numbers only."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class CaseInsensitiveStrEnum(StrEnum):
    """String enum that accepts values regardless of case or surrounding whitespace."""

    @classmethod
    def _missing_(cls, value: object) -> Self | None:
        if isinstance(value, str):
            key = value.strip().casefold()
            for member in cls:
                if member.value.casefold() == key:
                    return member
        return None


class RiskLevel(CaseInsensitiveStrEnum):
    """Issuer risk level / investor risk tolerance, in ascending order of risk."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def ordinal(self) -> int:
        """Position on the risk scale (low=0, medium=1, high=2)."""
        return list(RiskLevel).index(self)


class CompanyStage(CaseInsensitiveStrEnum):
    """Company lifecycle stage, declared in lifecycle order (used for adjacency scoring)."""

    SEED = "seed"
    EARLY = "early"
    GROWTH = "growth"
    LATE = "late"
    MATURE = "mature"

    @property
    def ordinal(self) -> int:
        """Position in the lifecycle (seed=0 ... mature=4)."""
        return list(CompanyStage).index(self)


class InvestorType(CaseInsensitiveStrEnum):
    """Categories of institutional investor represented in the synthetic dataset."""

    INSTITUTIONAL_ASSET_MANAGER = "Institutional Asset Manager"
    PENSION_FUND = "Pension Fund"
    INSURANCE_INVESTOR = "Insurance Investor"
    GROWTH_EQUITY_FUND = "Growth Equity Fund"
    TECHNOLOGY_FUND = "Technology Fund"
    INFRASTRUCTURE_FUND = "Infrastructure Fund"
    ESG_FOCUSED_FUND = "ESG-focused Fund"


Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_\-]*$"
    ),
]
"""Stable identifier such as ``INV-001``: letters, digits, ``-`` and ``_`` only."""

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
"""Free text that must contain at least one non-whitespace character."""

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
"""A sector or region label. Compared case-insensitively by the matching engine."""

Ticker = Annotated[
    str, StringConstraints(min_length=1, max_length=12, pattern=r"^[A-Z0-9][A-Z0-9.\-]*$")
]
"""Exchange ticker. Inputs are stripped and upper-cased before this pattern is applied."""
