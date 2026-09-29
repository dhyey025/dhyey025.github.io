"""Unit tests for the pure, deterministic matching engine."""

import itertools
import random
from typing import ClassVar

import pytest

from app.models.common import CompanyStage, RiskLevel
from app.services.matching_engine import (
    DEAL_SIZE_WEIGHT,
    MAX_TOTAL_SCORE,
    REGION_WEIGHT,
    RISK_WEIGHT,
    SECTOR_WEIGHT,
    STAGE_WEIGHT,
    Outcome,
    calculate_match,
    check_eligibility,
    fit_band,
    is_eligible,
    normalise_label,
    rank_investors,
    score_deal_size,
    score_region,
    score_risk,
    score_sector,
    score_stage,
)
from tests.factories import make_issuer, make_mandate


def test_weights_sum_to_100() -> None:
    weights = [SECTOR_WEIGHT, REGION_WEIGHT, DEAL_SIZE_WEIGHT, STAGE_WEIGHT, RISK_WEIGHT]
    assert weights == [30.0, 20.0, 20.0, 15.0, 15.0]
    assert sum(weights) == MAX_TOTAL_SCORE == 100.0


# =====================================================================================
# Normalisation
# =====================================================================================


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Technology", "technology"),
        ("  TECHNOLOGY  ", "technology"),
        ("Asia-Pacific", "asia pacific"),
        ("asia   pacific", "asia pacific"),
        ("ASIA_PACIFIC", "asia pacific"),
        ("Financial Services", "financial services"),
    ],
)
def test_normalise_label(raw: str, expected: str) -> None:
    assert normalise_label(raw) == expected


# =====================================================================================
# Sector (30)
# =====================================================================================


class TestScoreSector:
    def test_exact_match_scores_full_weight(self) -> None:
        result = score_sector(make_issuer(sector="Technology"), make_mandate())
        assert result.score == 30.0
        assert result.outcome is Outcome.MET

    @pytest.mark.parametrize(
        ("issuer_sector", "mandate_sector"),
        [
            ("technology", "Technology"),
            ("TECHNOLOGY", "technology"),
            ("Financial-Services", "financial services"),
            ("  Healthcare ", "HEALTHCARE"),
        ],
    )
    def test_matching_is_case_normalised(self, issuer_sector: str, mandate_sector: str) -> None:
        issuer = make_issuer(sector=issuer_sector)
        mandate = make_mandate(preferred_sectors=[mandate_sector])
        assert score_sector(issuer, mandate).score == 30.0

    def test_match_against_any_of_several_preferred_sectors(self) -> None:
        mandate = make_mandate(preferred_sectors=["Energy", "Healthcare", "Technology"])
        assert score_sector(make_issuer(sector="Healthcare"), mandate).score == 30.0

    def test_mismatch_scores_zero_and_explains(self) -> None:
        mandate = make_mandate(preferred_sectors=["Energy", "Infrastructure"])
        result = score_sector(make_issuer(sector="Technology"), mandate)
        assert result.score == 0.0
        assert result.outcome is Outcome.NOT_MET
        assert "Energy, Infrastructure" in result.reason

    def test_no_partial_matching_on_substrings(self) -> None:
        mandate = make_mandate(preferred_sectors=["Technology"])
        assert score_sector(make_issuer(sector="Tech"), mandate).score == 0.0


# =====================================================================================
# Region (20)
# =====================================================================================


class TestScoreRegion:
    def test_exact_match(self) -> None:
        result = score_region(make_issuer(region="UK"), make_mandate(preferred_regions=["UK"]))
        assert result.score == 20.0
        assert result.outcome is Outcome.MET
        assert result.reason == "'UK' is a preferred region"

    @pytest.mark.parametrize(
        ("issuer_region", "mandate_region"),
        [("north america", "North America"), ("asia pacific", "Asia-Pacific"), ("uk", "UK")],
    )
    def test_matching_is_case_normalised(self, issuer_region: str, mandate_region: str) -> None:
        issuer = make_issuer(region=issuer_region)
        mandate = make_mandate(preferred_regions=[mandate_region])
        assert score_region(issuer, mandate).score == 20.0

    def test_mismatch_scores_zero(self) -> None:
        issuer = make_issuer(region="Asia-Pacific")
        mandate = make_mandate(preferred_regions=["UK", "Europe"])
        result = score_region(issuer, mandate)
        assert result.score == 0.0
        assert result.outcome is Outcome.NOT_MET
        assert "UK, Europe" in result.reason

    @pytest.mark.parametrize(
        "issuer_region", ["UK", "Europe", "North America", "Asia-Pacific", "Latin America"]
    )
    def test_global_mandate_covers_every_region(self, issuer_region: str) -> None:
        mandate = make_mandate(preferred_regions=["Global"])
        result = score_region(make_issuer(region=issuer_region), mandate)
        assert result.score == 20.0
        assert "'Global' mandate region" in result.reason

    def test_global_mandate_is_case_insensitive(self) -> None:
        mandate = make_mandate(preferred_regions=["GLOBAL"])
        assert score_region(make_issuer(region="Europe"), mandate).score == 20.0

    def test_global_issuer_matches_only_global_mandates(self) -> None:
        issuer = make_issuer(region="Global")
        assert score_region(issuer, make_mandate(preferred_regions=["Global"])).score == 20.0
        regional = make_mandate(preferred_regions=["UK", "Europe", "North America"])
        assert score_region(issuer, regional).score == 0.0

    def test_europe_mandate_covers_uk_issuer(self) -> None:
        result = score_region(make_issuer(region="UK"), make_mandate(preferred_regions=["Europe"]))
        assert result.score == 20.0
        assert result.reason == "'UK' is covered by the 'Europe' mandate region"

    def test_uk_mandate_does_not_cover_europe_issuer(self) -> None:
        mandate = make_mandate(preferred_regions=["UK"])
        assert score_region(make_issuer(region="Europe"), mandate).score == 0.0

    def test_exact_region_is_reported_in_preference_to_broader_cover(self) -> None:
        mandate = make_mandate(preferred_regions=["Global", "Europe", "UK"])
        result = score_region(make_issuer(region="UK"), mandate)
        assert result.reason == "'UK' is a preferred region"


# =====================================================================================
# Deal size (20)
# =====================================================================================


class TestScoreDealSize:
    MANDATE_RANGE: ClassVar[dict[str, float]] = {"min_deal_size_m": 100.0, "max_deal_size_m": 500.0}

    @pytest.mark.parametrize(
        ("deal_size", "expected_score", "expected_outcome"),
        [
            (100.0, 20.0, Outcome.MET),  # minimum is inclusive
            (300.0, 20.0, Outcome.MET),
            (500.0, 20.0, Outcome.MET),  # maximum is inclusive
            (99.99, 10.0, Outcome.PARTIAL),  # just below minimum
            (80.0, 10.0, Outcome.PARTIAL),  # exactly 20% below minimum (inclusive)
            (79.99, 0.0, Outcome.NOT_MET),  # just beyond tolerance
            (500.01, 10.0, Outcome.PARTIAL),  # just above maximum
            (600.0, 10.0, Outcome.PARTIAL),  # exactly 20% above maximum (inclusive)
            (600.01, 0.0, Outcome.NOT_MET),
            (1.0, 0.0, Outcome.NOT_MET),
            (5000.0, 0.0, Outcome.NOT_MET),
        ],
    )
    def test_boundaries(
        self, deal_size: float, expected_score: float, expected_outcome: Outcome
    ) -> None:
        issuer = make_issuer(deal_size_m=deal_size)
        result = score_deal_size(issuer, make_mandate(**self.MANDATE_RANGE))
        assert result.score == expected_score
        assert result.outcome is expected_outcome

    def test_tolerance_boundary_is_robust_to_float_error(self) -> None:
        # Exactly 20% below the minimum, but (0.1 - 0.08) / 0.1 == 0.20000000000000004 in floats.
        assert (0.1 - 0.08) / 0.1 > 0.2
        mandate = make_mandate(min_deal_size_m=0.1, max_deal_size_m=1.0)
        assert score_deal_size(make_issuer(deal_size_m=0.08), mandate).score == 10.0

    def test_zero_minimum_accepts_small_deals(self) -> None:
        mandate = make_mandate(min_deal_size_m=0.0, max_deal_size_m=10.0)
        assert score_deal_size(make_issuer(deal_size_m=0.5), mandate).score == 20.0

    def test_single_point_range(self) -> None:
        mandate = make_mandate(min_deal_size_m=75.0, max_deal_size_m=75.0)
        assert score_deal_size(make_issuer(deal_size_m=75.0), mandate).score == 20.0

    def test_reason_quantifies_the_miss(self) -> None:
        issuer = make_issuer(deal_size_m=90.0)
        result = score_deal_size(issuer, make_mandate(**self.MANDATE_RANGE))
        assert result.reason == (
            "90m is 10% below the minimum of the 100m to 500m range, within the 20% tolerance"
        )


# =====================================================================================
# Company stage (15)
# =====================================================================================


class TestScoreStage:
    def test_preferred_stage_scores_full_weight(self) -> None:
        result = score_stage(make_issuer(company_stage="growth"), make_mandate())
        assert result.score == 15.0
        assert result.outcome is Outcome.MET

    def test_stage_input_is_case_insensitive(self) -> None:
        issuer = make_issuer(company_stage="GROWTH")
        mandate = make_mandate(preferred_stages=["Growth"])
        assert score_stage(issuer, mandate).score == 15.0

    @pytest.mark.parametrize("issuer_stage", ["early", "late"])
    def test_adjacent_stage_scores_half(self, issuer_stage: str) -> None:
        mandate = make_mandate(preferred_stages=["growth"])
        result = score_stage(make_issuer(company_stage=issuer_stage), mandate)
        assert result.score == 7.5
        assert result.outcome is Outcome.PARTIAL

    @pytest.mark.parametrize(("issuer_stage", "distance"), [("seed", 2), ("mature", 2)])
    def test_distant_stage_scores_zero(self, issuer_stage: str, distance: int) -> None:
        mandate = make_mandate(preferred_stages=["growth"])
        result = score_stage(make_issuer(company_stage=issuer_stage), mandate)
        assert result.score == 0.0
        assert result.outcome is Outcome.NOT_MET
        assert f"{distance} lifecycle steps" in result.reason

    def test_closest_preferred_stage_is_used(self) -> None:
        mandate = make_mandate(preferred_stages=["mature", "early"])
        assert score_stage(make_issuer(company_stage="seed"), mandate).score == 7.5

    def test_lifecycle_order(self) -> None:
        assert [s.value for s in sorted(CompanyStage, key=lambda s: s.ordinal)] == [
            "seed",
            "early",
            "growth",
            "late",
            "mature",
        ]


# =====================================================================================
# Risk (15)
# =====================================================================================


class TestScoreRisk:
    @pytest.mark.parametrize(
        ("issuer_risk", "tolerance", "expected_score", "expected_outcome"),
        [
            ("low", "low", 15.0, Outcome.MET),
            ("low", "medium", 15.0, Outcome.MET),
            ("low", "high", 15.0, Outcome.MET),
            ("medium", "low", 5.0, Outcome.PARTIAL),
            ("medium", "medium", 15.0, Outcome.MET),
            ("medium", "high", 15.0, Outcome.MET),
            ("high", "low", 0.0, Outcome.NOT_MET),
            ("high", "medium", 5.0, Outcome.PARTIAL),
            ("high", "high", 15.0, Outcome.MET),
        ],
    )
    def test_risk_matrix(
        self, issuer_risk: str, tolerance: str, expected_score: float, expected_outcome: Outcome
    ) -> None:
        issuer = make_issuer(risk_level=issuer_risk)
        mandate = make_mandate(risk_tolerance=tolerance)
        result = score_risk(issuer, mandate)
        assert result.score == expected_score
        assert result.outcome is expected_outcome


# =====================================================================================
# Eligibility
# =====================================================================================


class TestEligibility:
    def test_active_mandate_without_revenue_minimum_is_eligible(self) -> None:
        assert check_eligibility(make_issuer(), make_mandate()) == []

    def test_inactive_mandate_is_ineligible(self) -> None:
        mandate = make_mandate(active=False)
        assert check_eligibility(make_issuer(), mandate) == ["mandate is inactive"]
        assert not is_eligible(make_issuer(), mandate)

    def test_revenue_below_minimum_is_ineligible(self) -> None:
        reasons = check_eligibility(make_issuer(revenue_m=49.0), make_mandate(min_revenue_m=50.0))
        assert reasons == ["issuer revenue 49m is below the 50m minimum"]

    def test_revenue_equal_to_minimum_is_eligible(self) -> None:
        assert is_eligible(make_issuer(revenue_m=50.0), make_mandate(min_revenue_m=50.0))

    def test_pre_revenue_issuer_is_eligible_when_no_minimum(self) -> None:
        assert is_eligible(make_issuer(revenue_m=0.0), make_mandate(min_revenue_m=None))

    def test_all_reasons_are_reported(self) -> None:
        mandate = make_mandate(active=False, min_revenue_m=100.0)
        assert len(check_eligibility(make_issuer(revenue_m=1.0), mandate)) == 2


# =====================================================================================
# calculate_match - known cases with explicitly asserted components
# =====================================================================================


class TestCalculateMatchKnownCases:
    def test_perfect_match(self) -> None:
        issuer = make_issuer(
            sector="Technology",
            region="UK",
            deal_size_m=50.0,
            revenue_m=30.0,
            company_stage="growth",
            risk_level="high",
        )
        mandate = make_mandate(
            id="INV-KNOWN-1",
            investor_name="Known Case Fund",
            preferred_sectors=["Healthcare", "Technology"],
            preferred_regions=["UK", "Europe"],
            min_deal_size_m=10.0,
            max_deal_size_m=80.0,
            min_revenue_m=5.0,
            preferred_stages=["early", "growth"],
            risk_tolerance="high",
        )

        result = calculate_match(issuer, mandate)

        assert result.investor_id == "INV-KNOWN-1"
        assert result.sector_score == 30.0
        assert result.region_score == 20.0
        assert result.deal_size_score == 20.0
        assert result.stage_score == 15.0
        assert result.risk_score == 15.0
        assert result.total_score == 100.0
        assert len(result.matched_criteria) == 5
        assert result.partially_matched_criteria == []
        assert result.unmatched_criteria == []
        assert result.explanation.startswith(
            "Strong match for Known Case Fund with a score of 100/100."
        )
        assert "issuer revenue 30m meets the 5m minimum" in result.explanation

    def test_mixed_match(self) -> None:
        """Sector miss, region via parent, and three different partial credits.

        sector 0 + region 20 + deal size 10 + stage 7.5 + risk 5 = 42.5
        """
        issuer = make_issuer(
            sector="Consumer",
            region="UK",
            deal_size_m=90.0,  # 20% above the 75m maximum -> near miss
            company_stage="late",  # adjacent to growth
            risk_level="high",  # one level above medium tolerance
        )
        mandate = make_mandate(
            investor_name="Mixed Case Partners",
            preferred_sectors=["Technology"],
            preferred_regions=["Europe"],
            min_deal_size_m=10.0,
            max_deal_size_m=75.0,
            preferred_stages=["growth"],
            risk_tolerance="medium",
        )

        result = calculate_match(issuer, mandate)

        assert result.sector_score == 0.0
        assert result.region_score == 20.0
        assert result.deal_size_score == 10.0
        assert result.stage_score == 7.5
        assert result.risk_score == 5.0
        assert result.total_score == 42.5
        assert result.matched_criteria == [
            "Region (20/20): 'UK' is covered by the 'Europe' mandate region"
        ]
        assert result.partially_matched_criteria == [
            "Deal size (10/20): 90m is 20% above the maximum of the 10m to 75m range, "
            "within the 20% tolerance",
            "Company stage (7.5/15): 'late' is adjacent to the preferred stages: growth",
            "Risk (5/15): issuer risk 'high' exceeds the 'medium' risk tolerance by one level",
        ]
        assert result.unmatched_criteria == [
            "Sector (0/30): 'Consumer' is not among the preferred sectors: Technology"
        ]
        assert result.explanation.startswith(
            "Limited match for Mixed Case Partners with a score of 42.5/100."
        )
        assert "has no minimum revenue requirement" in result.explanation

    def test_zero_match(self) -> None:
        issuer = make_issuer(
            sector="Energy",
            region="Asia-Pacific",
            deal_size_m=5000.0,
            company_stage="seed",
            risk_level="high",
        )
        mandate = make_mandate(
            preferred_sectors=["Healthcare"],
            preferred_regions=["UK"],
            min_deal_size_m=10.0,
            max_deal_size_m=100.0,
            preferred_stages=["mature"],
            risk_tolerance="low",
        )
        result = calculate_match(issuer, mandate)
        assert result.total_score == 0.0
        assert len(result.unmatched_criteria) == 5
        assert result.explanation.startswith("Weak match")

    def test_explanation_flags_ineligible_mandate_when_scored_directly(self) -> None:
        result = calculate_match(make_issuer(), make_mandate(active=False))
        assert "Not eligible for recommendation: mandate is inactive." in result.explanation

    def test_total_equals_sum_of_components(self) -> None:
        result = calculate_match(make_issuer(company_stage="late"), make_mandate())
        components = (
            result.sector_score
            + result.region_score
            + result.deal_size_score
            + result.stage_score
            + result.risk_score
        )
        assert result.total_score == round(components, 2)


@pytest.mark.parametrize(
    ("score", "band"),
    [(100.0, "Strong"), (80.0, "Strong"), (79.99, "Moderate"), (60.0, "Moderate"),
     (40.0, "Limited"), (39.99, "Weak"), (0.0, "Weak")],
)  # fmt: skip
def test_fit_band_thresholds(score: float, band: str) -> None:
    assert fit_band(score) == band


# =====================================================================================
# Score bounds - exhaustive grid over every scoring dimension
# =====================================================================================


def test_scores_stay_within_bounds_across_all_combinations() -> None:
    """Total is always in [0, 100], each component in [0, weight], total == sum."""
    sector_cases = [("Technology", ["Technology"]), ("Energy", ["Technology"])]
    region_cases = [("UK", ["UK"]), ("UK", ["Europe"]), ("Europe", ["UK"]), ("UK", ["Global"])]
    deal_sizes = [1.0, 8.0, 10.0, 50.0, 100.0, 120.0, 121.0, 10_000.0]

    grid = itertools.product(
        sector_cases, region_cases, deal_sizes, CompanyStage, CompanyStage, RiskLevel, RiskLevel
    )
    checked = 0
    for combination in grid:
        (sector, sectors), (region, regions), deal, stage, pref_stage, risk, tolerance = combination
        issuer = make_issuer(
            sector=sector, region=region, deal_size_m=deal, company_stage=stage, risk_level=risk
        )
        mandate = make_mandate(
            preferred_sectors=sectors,
            preferred_regions=regions,
            min_deal_size_m=10.0,
            max_deal_size_m=100.0,
            preferred_stages=[pref_stage],
            risk_tolerance=tolerance,
        )
        result = calculate_match(issuer, mandate)

        assert 0.0 <= result.total_score <= 100.0
        assert 0.0 <= result.sector_score <= SECTOR_WEIGHT
        assert 0.0 <= result.region_score <= REGION_WEIGHT
        assert 0.0 <= result.deal_size_score <= DEAL_SIZE_WEIGHT
        assert 0.0 <= result.stage_score <= STAGE_WEIGHT
        assert 0.0 <= result.risk_score <= RISK_WEIGHT
        checked += 1

    assert checked == 2 * 4 * 8 * 5 * 5 * 3 * 3


# =====================================================================================
# Ranking
# =====================================================================================


class TestRankInvestors:
    def test_results_are_ordered_highest_score_first(self) -> None:
        issuer = make_issuer(sector="Technology", region="UK", company_stage="growth")
        mandates = [
            make_mandate(id="INV-LOW", preferred_sectors=["Energy"], preferred_regions=["Asia"]),
            make_mandate(id="INV-HIGH"),
            make_mandate(id="INV-MID", preferred_sectors=["Energy"]),
        ]
        ranked = rank_investors(issuer, mandates)
        assert [r.investor_id for r in ranked] == ["INV-HIGH", "INV-MID", "INV-LOW"]
        scores = [r.total_score for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_ties_are_broken_by_investor_id(self) -> None:
        mandates = [make_mandate(id="INV-C"), make_mandate(id="INV-A"), make_mandate(id="INV-B")]
        ranked = rank_investors(make_issuer(), mandates)
        assert [r.investor_id for r in ranked] == ["INV-A", "INV-B", "INV-C"]

    def test_inactive_mandates_are_never_returned(self) -> None:
        perfect_but_inactive = make_mandate(id="INV-INACTIVE", active=False)
        weak_but_active = make_mandate(id="INV-ACTIVE", preferred_sectors=["Energy"])
        ranked = rank_investors(make_issuer(), [perfect_but_inactive, weak_but_active])
        assert [r.investor_id for r in ranked] == ["INV-ACTIVE"]

    def test_mandates_above_issuer_revenue_are_excluded(self) -> None:
        mandates = [
            make_mandate(id="INV-TOO-BIG", min_revenue_m=500.0),
            make_mandate(id="INV-OK", min_revenue_m=10.0),
        ]
        ranked = rank_investors(make_issuer(revenue_m=30.0), mandates)
        assert [r.investor_id for r in ranked] == ["INV-OK"]

    def test_no_eligible_mandates_returns_empty_list(self) -> None:
        assert rank_investors(make_issuer(), [make_mandate(active=False)]) == []
        assert rank_investors(make_issuer(), []) == []


# =====================================================================================
# Reproducibility
# =====================================================================================


class TestDeterminism:
    def test_calculate_match_is_reproducible(self) -> None:
        issuer = make_issuer(company_stage="late", deal_size_m=110.0)
        mandate = make_mandate()
        first = calculate_match(issuer, mandate)
        for _ in range(10):
            again = calculate_match(issuer, mandate)
            assert again == first
            assert again.model_dump_json() == first.model_dump_json()

    def test_ranking_is_independent_of_input_order(self) -> None:
        issuer = make_issuer()
        mandates = [
            make_mandate(id=f"INV-{i:03d}", preferred_stages=[stage], risk_tolerance=risk)
            for i, (stage, risk) in enumerate(itertools.product(CompanyStage, RiskLevel))
        ]
        expected = rank_investors(issuer, mandates)
        for seed in range(5):
            shuffled = mandates.copy()
            random.Random(seed).shuffle(shuffled)
            assert rank_investors(issuer, shuffled) == expected
