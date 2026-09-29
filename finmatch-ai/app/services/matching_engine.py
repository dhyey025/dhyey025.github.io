"""Deterministic investor-matching engine.

Everything in this module is a pure function: no I/O, no randomness, no clock, no
network and no LLM. The same issuer and mandates always produce the same scores,
ordering and explanation text. The module deliberately has no web or database
dependencies so it can later be exposed to an agent as a tool without the agent
being able to change how scores are calculated.

Full specification: ``docs/matching-methodology.md``.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from app.models.investor import InvestorMandate
from app.models.issuer import IssuerProfile
from app.models.match import MatchResult

SCORING_VERSION: Final = "1.0.0"

# --- Component weights (sum to 100) ------------------------------------------------
SECTOR_WEIGHT: Final = 30.0
REGION_WEIGHT: Final = 20.0
DEAL_SIZE_WEIGHT: Final = 20.0
STAGE_WEIGHT: Final = 15.0
RISK_WEIGHT: Final = 15.0
MAX_TOTAL_SCORE: Final = (
    SECTOR_WEIGHT + REGION_WEIGHT + DEAL_SIZE_WEIGHT + STAGE_WEIGHT + RISK_WEIGHT
)

# --- Partial-credit rules ----------------------------------------------------------
DEAL_SIZE_TOLERANCE: Final = 0.20
"""A deal up to 20% outside the nearest mandate bound is a near miss."""
DEAL_SIZE_NEAR_MISS_CREDIT: Final = 0.5
STAGE_ADJACENT_CREDIT: Final = 0.5
"""A stage one lifecycle step from a preferred stage earns half credit."""
RISK_ONE_LEVEL_OVER_CREDIT: Final = 1 / 3
"""Issuer risk one level above tolerance earns a third of the risk weight (5 of 15)."""

# --- Region rules ------------------------------------------------------------------
GLOBAL_REGION: Final = "global"
REGION_PARENTS: Final[Mapping[str, str]] = MappingProxyType({"uk": "europe"})
"""Sub-region -> broader region that covers it (normalised labels). UK is part of Europe."""

# --- Explanation bands (by total score) --------------------------------------------
FIT_BANDS: Final[tuple[tuple[float, str], ...]] = (
    (80.0, "Strong"),
    (60.0, "Moderate"),
    (40.0, "Limited"),
    (0.0, "Weak"),
)

_FLOAT_TOLERANCE: Final = 1e-9


class Outcome(StrEnum):
    """How well a single criterion was satisfied."""

    MET = "met"
    PARTIAL = "partial"
    NOT_MET = "not_met"


@dataclass(frozen=True, slots=True)
class CriterionScore:
    """Score and human-readable reason for one scoring criterion."""

    criterion: str
    score: float
    max_score: float
    outcome: Outcome
    reason: str

    def describe(self) -> str:
        """E.g. ``"Sector (30/30): 'Technology' is a preferred sector"``."""
        return (
            f"{self.criterion} ({_fmt_points(self.score)}/{_fmt_points(self.max_score)}): "
            f"{self.reason}"
        )


# ==================================================================================
# Normalisation
# ==================================================================================


def normalise_label(value: str) -> str:
    """Canonical form used for all sector/region comparisons.

    Case-insensitive; hyphens, underscores and repeated whitespace are equivalent, so
    ``" Asia-Pacific "``, ``"asia pacific"`` and ``"ASIA_PACIFIC"`` all compare equal.
    """
    return " ".join(value.replace("-", " ").replace("_", " ").casefold().split())


# ==================================================================================
# Eligibility (hard filters, applied before scoring)
# ==================================================================================


def check_eligibility(issuer: IssuerProfile, mandate: InvestorMandate) -> list[str]:
    """Return the reasons a mandate is ineligible for this issuer (empty list = eligible)."""
    reasons: list[str] = []
    if not mandate.active:
        reasons.append("mandate is inactive")
    if mandate.min_revenue_m is not None and issuer.revenue_m < mandate.min_revenue_m:
        reasons.append(
            f"issuer revenue {_fmt_m(issuer.revenue_m)} is below the "
            f"{_fmt_m(mandate.min_revenue_m)} minimum"
        )
    return reasons


def is_eligible(issuer: IssuerProfile, mandate: InvestorMandate) -> bool:
    """True if the mandate may be recommended for this issuer."""
    return not check_eligibility(issuer, mandate)


# ==================================================================================
# Component scoring functions
# ==================================================================================


def score_sector(issuer: IssuerProfile, mandate: InvestorMandate) -> CriterionScore:
    """30 points if the issuer's sector is one of the mandate's preferred sectors, else 0."""
    preferred = {normalise_label(sector) for sector in mandate.preferred_sectors}
    if normalise_label(issuer.sector) in preferred:
        return _criterion(
            "Sector", SECTOR_WEIGHT, 1.0, Outcome.MET, f"'{issuer.sector}' is a preferred sector"
        )
    return _criterion(
        "Sector",
        SECTOR_WEIGHT,
        0.0,
        Outcome.NOT_MET,
        f"'{issuer.sector}' is not among the preferred sectors: "
        f"{', '.join(mandate.preferred_sectors)}",
    )


def score_region(issuer: IssuerProfile, mandate: InvestorMandate) -> CriterionScore:
    """20 points if any mandate region covers the issuer's region, else 0.

    A mandate region covers the issuer region if it is the same region, the broader
    parent region (``Europe`` covers ``UK``) or ``Global``.
    """
    covering = _covering_region(normalise_label(issuer.region), mandate.preferred_regions)
    if covering is None:
        return _criterion(
            "Region",
            REGION_WEIGHT,
            0.0,
            Outcome.NOT_MET,
            f"'{issuer.region}' is outside the mandate regions: "
            f"{', '.join(mandate.preferred_regions)}",
        )
    if normalise_label(covering) == normalise_label(issuer.region):
        reason = f"'{issuer.region}' is a preferred region"
    else:
        reason = f"'{issuer.region}' is covered by the '{covering}' mandate region"
    return _criterion("Region", REGION_WEIGHT, 1.0, Outcome.MET, reason)


def score_deal_size(issuer: IssuerProfile, mandate: InvestorMandate) -> CriterionScore:
    """20 points inside the mandate range (inclusive), 10 for a near miss, else 0.

    A near miss is a deal no more than ``DEAL_SIZE_TOLERANCE`` (20%) below the minimum
    or above the maximum, measured relative to the bound that was missed.
    """
    deal, low, high = issuer.deal_size_m, mandate.min_deal_size_m, mandate.max_deal_size_m
    range_text = f"the {_fmt_m(low)} to {_fmt_m(high)} range"
    if low <= deal <= high:
        return _criterion(
            "Deal size",
            DEAL_SIZE_WEIGHT,
            1.0,
            Outcome.MET,
            f"{_fmt_m(deal)} is within {range_text}",
        )

    # deal > 0 is guaranteed by validation, so deal < low implies low > 0; high > 0 likewise.
    if deal < low:
        gap, direction = (low - deal) / low, "below the minimum of"
    else:
        gap, direction = (deal - high) / high, "above the maximum of"
    position = f"{_fmt_m(deal)} is {_fmt_pct(gap)} {direction} {range_text}"

    if gap <= DEAL_SIZE_TOLERANCE + _FLOAT_TOLERANCE:
        return _criterion(
            "Deal size",
            DEAL_SIZE_WEIGHT,
            DEAL_SIZE_NEAR_MISS_CREDIT,
            Outcome.PARTIAL,
            f"{position}, within the {_fmt_pct(DEAL_SIZE_TOLERANCE)} tolerance",
        )
    return _criterion("Deal size", DEAL_SIZE_WEIGHT, 0.0, Outcome.NOT_MET, position)


def score_stage(issuer: IssuerProfile, mandate: InvestorMandate) -> CriterionScore:
    """15 points for a preferred stage, 7.5 for an adjacent lifecycle stage, else 0."""
    stage = issuer.company_stage
    preferred = sorted(set(mandate.preferred_stages), key=lambda s: s.ordinal)
    preferred_text = ", ".join(s.value for s in preferred)
    if stage in preferred:
        return _criterion(
            "Company stage", STAGE_WEIGHT, 1.0, Outcome.MET, f"'{stage}' is a preferred stage"
        )
    distance = min(abs(stage.ordinal - p.ordinal) for p in preferred)
    if distance == 1:
        return _criterion(
            "Company stage",
            STAGE_WEIGHT,
            STAGE_ADJACENT_CREDIT,
            Outcome.PARTIAL,
            f"'{stage}' is adjacent to the preferred stages: {preferred_text}",
        )
    return _criterion(
        "Company stage",
        STAGE_WEIGHT,
        0.0,
        Outcome.NOT_MET,
        f"'{stage}' is {distance} lifecycle steps from the preferred stages: {preferred_text}",
    )


def score_risk(issuer: IssuerProfile, mandate: InvestorMandate) -> CriterionScore:
    """Risk tolerance is a ceiling: 15 points at or below it, 5 one level above, 0 two above.

    Matrix (rows = issuer risk, columns = investor tolerance)::

                  low  medium  high
        low        15     15     15
        medium      5     15     15
        high        0      5     15
    """
    risk, tolerance = issuer.risk_level, mandate.risk_tolerance
    levels_over = risk.ordinal - tolerance.ordinal
    if levels_over <= 0:
        return _criterion(
            "Risk",
            RISK_WEIGHT,
            1.0,
            Outcome.MET,
            f"issuer risk '{risk}' is within the '{tolerance}' risk tolerance",
        )
    if levels_over == 1:
        return _criterion(
            "Risk",
            RISK_WEIGHT,
            RISK_ONE_LEVEL_OVER_CREDIT,
            Outcome.PARTIAL,
            f"issuer risk '{risk}' exceeds the '{tolerance}' risk tolerance by one level",
        )
    return _criterion(
        "Risk",
        RISK_WEIGHT,
        0.0,
        Outcome.NOT_MET,
        f"issuer risk '{risk}' exceeds the '{tolerance}' risk tolerance by {levels_over} levels",
    )


# ==================================================================================
# Aggregation and ranking
# ==================================================================================


def calculate_match(issuer: IssuerProfile, mandate: InvestorMandate) -> MatchResult:
    """Score one mandate against an issuer and explain the result.

    This scores any mandate it is given; eligibility filtering is the job of
    :func:`rank_investors`, which is the only path used for recommendations. The
    explanation still states eligibility so a directly scored mandate is never
    misrepresented.
    """
    sector = score_sector(issuer, mandate)
    region = score_region(issuer, mandate)
    deal_size = score_deal_size(issuer, mandate)
    stage = score_stage(issuer, mandate)
    risk = score_risk(issuer, mandate)
    components = (sector, region, deal_size, stage, risk)
    total = round(sum(c.score for c in components), 2)

    return MatchResult(
        investor_id=mandate.id,
        investor_name=mandate.investor_name,
        investor_type=mandate.investor_type,
        total_score=total,
        sector_score=sector.score,
        region_score=region.score,
        deal_size_score=deal_size.score,
        stage_score=stage.score,
        risk_score=risk.score,
        matched_criteria=[c.describe() for c in components if c.outcome is Outcome.MET],
        partially_matched_criteria=[
            c.describe() for c in components if c.outcome is Outcome.PARTIAL
        ],
        unmatched_criteria=[c.describe() for c in components if c.outcome is Outcome.NOT_MET],
        explanation=build_explanation(issuer, mandate, total, components),
    )


def rank_investors(issuer: IssuerProfile, mandates: Iterable[InvestorMandate]) -> list[MatchResult]:
    """Score all eligible mandates, highest total first.

    Ineligible mandates (inactive, or issuer revenue below the mandate minimum) are
    removed *before* scoring and can never appear in the output. Ties are broken by
    ``investor_id`` ascending so ordering is fully deterministic.
    """
    results = [calculate_match(issuer, m) for m in mandates if is_eligible(issuer, m)]
    return sorted(results, key=lambda r: (-r.total_score, r.investor_id))


def fit_band(total_score: float) -> str:
    """Qualitative label for a total score (used only in explanation text)."""
    for threshold, label in FIT_BANDS:
        if total_score >= threshold:
            return label
    return FIT_BANDS[-1][1]


def build_explanation(
    issuer: IssuerProfile,
    mandate: InvestorMandate,
    total_score: float,
    components: Sequence[CriterionScore],
) -> str:
    """Deterministic, template-based explanation of a match (no LLM involved)."""
    sentences = [
        f"{fit_band(total_score)} match for {mandate.investor_name} "
        f"with a score of {_fmt_points(total_score)}/{_fmt_points(MAX_TOTAL_SCORE)}."
    ]
    for outcome, prefix in (
        (Outcome.MET, "Aligned on"),
        (Outcome.PARTIAL, "Partially aligned on"),
        (Outcome.NOT_MET, "Not aligned on"),
    ):
        phrases = [
            f"{c.criterion.lower()} ({c.reason})" for c in components if c.outcome is outcome
        ]
        if phrases:
            sentences.append(f"{prefix} {_join_phrases(phrases)}.")

    ineligible = check_eligibility(issuer, mandate)
    if ineligible:
        sentences.append(f"Not eligible for recommendation: {_join_phrases(ineligible)}.")
    elif mandate.min_revenue_m is None:
        sentences.append("Eligibility: mandate is active and has no minimum revenue requirement.")
    else:
        sentences.append(
            f"Eligibility: mandate is active and issuer revenue {_fmt_m(issuer.revenue_m)} "
            f"meets the {_fmt_m(mandate.min_revenue_m)} minimum."
        )
    return " ".join(sentences)


# ==================================================================================
# Helpers
# ==================================================================================


def _criterion(
    criterion: str, weight: float, credit: float, outcome: Outcome, reason: str
) -> CriterionScore:
    return CriterionScore(
        criterion=criterion,
        score=round(weight * credit, 2),
        max_score=weight,
        outcome=outcome,
        reason=reason,
    )


def _covering_region(issuer_region: str, mandate_regions: Sequence[str]) -> str | None:
    """Return the mandate region label covering the issuer region, most specific first."""
    by_normalised = {normalise_label(region): region for region in mandate_regions}
    for candidate in (issuer_region, REGION_PARENTS.get(issuer_region), GLOBAL_REGION):
        if candidate is not None and candidate in by_normalised:
            return by_normalised[candidate]
    return None


def _fmt_points(value: float) -> str:
    return f"{value:g}"


def _fmt_m(value: float) -> str:
    """Format USD millions compactly: 50.0 -> '50m', 12.5 -> '12.5m', 1500 -> '1,500m'."""
    return f"{value:,.2f}".rstrip("0").rstrip(".") + "m"


def _fmt_pct(ratio: float) -> str:
    """0.125 -> '12.5%', 0.2 -> '20%'."""
    return f"{ratio * 100:.1f}".rstrip("0").rstrip(".") + "%"


def _join_phrases(phrases: Sequence[str]) -> str:
    if len(phrases) <= 1:
        return "".join(phrases)
    return f"{', '.join(phrases[:-1])} and {phrases[-1]}"
