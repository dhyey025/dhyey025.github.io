"""Match result and response models."""

import math
from typing import Self

from pydantic import Field, model_validator

from app.models.common import DomainModel, InvestorType
from app.models.issuer import IssuerProfile


class MatchResult(DomainModel):
    """Deterministic score of one investor mandate against one issuer.

    Every component score is exposed so the total can be recomputed by hand. The
    validator guarantees the total is exactly the (rounded) sum of its components.
    """

    investor_id: str
    investor_name: str
    investor_type: InvestorType

    total_score: float = Field(ge=0, le=100)
    sector_score: float = Field(ge=0)
    region_score: float = Field(ge=0)
    deal_size_score: float = Field(ge=0)
    stage_score: float = Field(ge=0)
    risk_score: float = Field(ge=0)

    matched_criteria: list[str]
    partially_matched_criteria: list[str]
    unmatched_criteria: list[str]

    explanation: str = Field(description="Deterministic, template-generated explanation.")

    @model_validator(mode="after")
    def _total_is_sum_of_components(self) -> Self:
        component_sum = round(
            self.sector_score
            + self.region_score
            + self.deal_size_score
            + self.stage_score
            + self.risk_score,
            2,
        )
        if not math.isclose(self.total_score, component_sum, abs_tol=1e-9):
            raise ValueError(
                f"total_score {self.total_score} does not equal sum of components {component_sum}"
            )
        return self


class MatchResponse(DomainModel):
    """Ranked matches for an issuer, highest total score first."""

    issuer: IssuerProfile
    scoring_version: str = Field(description="Version of the deterministic scoring methodology.")
    number_of_candidates: int = Field(
        ge=0, description="Eligible mandates scored, before top_n truncation."
    )
    matches: list[MatchResult]
