"""POST /api/v1/matches."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.main import create_app
from tests.conftest import make_settings, running_client
from tests.factories import issuer_payload, mandate_payload

MATCHES_URL = "/api/v1/matches"
INACTIVE_IDS = {"INV-016", "INV-017"}


def fintech_issuer(**overrides: Any) -> dict[str, Any]:
    """A UK growth-stage technology company used across API tests."""
    defaults: dict[str, Any] = {
        "id": "ISS-001",
        "company_name": "Lumenfield Analytics Ltd",
        "sector": "Technology",
        "region": "UK",
        "deal_size_m": 50,
        "revenue_m": 150,
        "company_stage": "growth",
        "risk_level": "high",
    }
    return issuer_payload(**(defaults | overrides))


async def test_response_structure(client: AsyncClient) -> None:
    response = await client.post(MATCHES_URL, json=fintech_issuer())
    assert response.status_code == 200
    body = response.json()

    assert body["issuer"]["id"] == "ISS-001"
    assert body["scoring_version"] == "1.0.0"
    assert body["number_of_candidates"] >= len(body["matches"]) > 0
    first = body["matches"][0]
    for key in (
        "investor_id",
        "investor_name",
        "total_score",
        "sector_score",
        "region_score",
        "deal_size_score",
        "stage_score",
        "risk_score",
        "matched_criteria",
        "partially_matched_criteria",
        "unmatched_criteria",
        "explanation",
    ):
        assert key in first


async def test_known_case_against_synthetic_dataset(client: AsyncClient) -> None:
    """INV-003 (Meridale, Global, 50-1000m, medium risk) vs a high-risk UK tech issuer.

    sector 30 + region 20 (Global) + deal 20 (50m is the inclusive minimum)
    + stage 15 + risk 5 (high is one level above medium) = 90
    """
    body = (await client.post(MATCHES_URL, params={"top_n": 50}, json=fintech_issuer())).json()
    meridale = next(m for m in body["matches"] if m["investor_id"] == "INV-003")

    assert meridale["sector_score"] == 30
    assert meridale["region_score"] == 20
    assert meridale["deal_size_score"] == 20
    assert meridale["stage_score"] == 15
    assert meridale["risk_score"] == 5
    assert meridale["total_score"] == 90
    assert meridale["partially_matched_criteria"] == [
        "Risk (5/15): issuer risk 'high' exceeds the 'medium' risk tolerance by one level"
    ]


async def test_matches_are_ordered_highest_score_first(client: AsyncClient) -> None:
    body = (await client.post(MATCHES_URL, params={"top_n": 50}, json=fintech_issuer())).json()
    ranking = [(-m["total_score"], m["investor_id"]) for m in body["matches"]]
    assert ranking == sorted(ranking)


async def test_all_scores_are_within_bounds(client: AsyncClient) -> None:
    body = (await client.post(MATCHES_URL, params={"top_n": 50}, json=fintech_issuer())).json()
    for match in body["matches"]:
        assert 0 <= match["total_score"] <= 100


@pytest.mark.parametrize(("top_n", "expected"), [(1, 1), (3, 3), (5, 5)])
async def test_top_n_limits_results(client: AsyncClient, top_n: int, expected: int) -> None:
    response = await client.post(MATCHES_URL, params={"top_n": top_n}, json=fintech_issuer())
    assert response.status_code == 200
    assert len(response.json()["matches"]) == expected


async def test_top_n_defaults_to_10(client: AsyncClient) -> None:
    # A high-revenue issuer clears every revenue threshold, leaving >10 candidates.
    body = (await client.post(MATCHES_URL, json=fintech_issuer(revenue_m=1000))).json()
    assert body["number_of_candidates"] > 10
    assert len(body["matches"]) == 10


async def test_top_n_larger_than_candidates_returns_all(client: AsyncClient) -> None:
    body = (await client.post(MATCHES_URL, params={"top_n": 50}, json=fintech_issuer())).json()
    assert len(body["matches"]) == body["number_of_candidates"]


async def test_top_n_does_not_change_ranking(client: AsyncClient) -> None:
    full = (await client.post(MATCHES_URL, params={"top_n": 50}, json=fintech_issuer())).json()
    top3 = (await client.post(MATCHES_URL, params={"top_n": 3}, json=fintech_issuer())).json()
    assert top3["matches"] == full["matches"][:3]
    assert top3["number_of_candidates"] == full["number_of_candidates"]


@pytest.mark.parametrize("top_n", ["0", "-1", "51", "abc", "2.5"])
async def test_invalid_top_n_is_rejected(client: AsyncClient, top_n: str) -> None:
    response = await client.post(MATCHES_URL, params={"top_n": top_n}, json=fintech_issuer())
    assert response.status_code == 422


async def test_inactive_mandates_never_appear(client: AsyncClient) -> None:
    # INV-016 (inactive) would be a perfect match for this issuer if it were active.
    consumer_issuer = issuer_payload(
        sector="Consumer",
        region="North America",
        deal_size_m=100,
        revenue_m=500,
        company_stage="growth",
        risk_level="medium",
    )
    body = (await client.post(MATCHES_URL, params={"top_n": 50}, json=consumer_issuer)).json()
    returned_ids = {m["investor_id"] for m in body["matches"]}
    assert returned_ids
    assert returned_ids.isdisjoint(INACTIVE_IDS)
    assert body["number_of_candidates"] == 18  # every active mandate is revenue-eligible


async def test_inactive_perfect_match_is_excluded_from_custom_dataset(
    write_dataset: Callable[[list[dict[str, Any]]], Path],
) -> None:
    path = write_dataset(
        [
            mandate_payload(id="INV-PERFECT-INACTIVE", active=False),
            mandate_payload(id="INV-WEAK-ACTIVE", preferred_sectors=["Energy"]),
        ]
    )
    async with running_client(create_app(make_settings(path))) as client:
        body = (await client.post(MATCHES_URL, json=issuer_payload())).json()

    assert body["number_of_candidates"] == 1
    assert [m["investor_id"] for m in body["matches"]] == ["INV-WEAK-ACTIVE"]


async def test_revenue_threshold_excludes_mandates(client: AsyncClient) -> None:
    investors = (await client.get("/api/v1/investors")).json()["investors"]
    min_revenue = {i["id"]: i["min_revenue_m"] for i in investors}

    body = (
        await client.post(MATCHES_URL, params={"top_n": 50}, json=fintech_issuer(revenue_m=0))
    ).json()

    returned = [m["investor_id"] for m in body["matches"]]
    assert returned  # mandates without a revenue minimum remain eligible
    assert all(min_revenue[i] is None for i in returned)


async def test_no_eligible_candidates_returns_empty_matches(
    write_dataset: Callable[[list[dict[str, Any]]], Path],
) -> None:
    path = write_dataset([mandate_payload(active=False)])
    async with running_client(create_app(make_settings(path))) as client:
        response = await client.post(MATCHES_URL, json=issuer_payload())

    assert response.status_code == 200
    assert response.json()["number_of_candidates"] == 0
    assert response.json()["matches"] == []


async def test_matching_is_case_normalised_end_to_end(client: AsyncClient) -> None:
    canonical = (await client.post(MATCHES_URL, json=fintech_issuer())).json()
    shouty = (
        await client.post(
            MATCHES_URL,
            json=fintech_issuer(sector="TECHNOLOGY", region="uk", company_stage="GROWTH"),
        )
    ).json()

    def scores(body: dict[str, Any]) -> list[tuple[str, float]]:
        return [(m["investor_id"], m["total_score"]) for m in body["matches"]]

    assert scores(shouty) == scores(canonical)


async def test_results_are_reproducible(client: AsyncClient) -> None:
    first = await client.post(MATCHES_URL, params={"top_n": 50}, json=fintech_issuer())
    second = await client.post(MATCHES_URL, params={"top_n": 50}, json=fintech_issuer())
    assert first.content == second.content


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"company_name": ""}, id="empty-company-name"),
        pytest.param({"company_name": "   "}, id="blank-company-name"),
        pytest.param({"sector": ""}, id="empty-sector"),
        pytest.param({"region": ""}, id="empty-region"),
        pytest.param({"deal_size_m": -10}, id="negative-deal-size"),
        pytest.param({"deal_size_m": 0}, id="zero-deal-size"),
        pytest.param({"deal_size_m": "lots"}, id="non-numeric-deal-size"),
        pytest.param({"revenue_m": -1}, id="negative-revenue"),
        pytest.param({"risk_level": "extreme"}, id="invalid-risk-level"),
        pytest.param({"company_stage": "unicorn"}, id="invalid-stage"),
        pytest.param({"surprise": True}, id="unknown-field"),
    ],
)
async def test_invalid_issuer_payload_is_rejected(
    client: AsyncClient, overrides: dict[str, Any]
) -> None:
    response = await client.post(MATCHES_URL, json=issuer_payload(**overrides))
    assert response.status_code == 422
    assert response.json()["detail"]


async def test_missing_field_is_rejected(client: AsyncClient) -> None:
    payload = issuer_payload()
    del payload["sector"]
    response = await client.post(MATCHES_URL, json=payload)
    assert response.status_code == 422


async def test_malformed_json_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        MATCHES_URL, content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
