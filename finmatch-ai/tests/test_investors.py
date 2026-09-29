"""Investor mandate endpoints."""

from httpx import AsyncClient

from app.models import InvestorMandate


async def test_list_investors(client: AsyncClient) -> None:
    response = await client.get("/api/v1/investors")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == len(body["investors"]) == 20
    # Every record round-trips through the domain model.
    for record in body["investors"]:
        InvestorMandate.model_validate(record)


async def test_list_investors_filtered_by_active(client: AsyncClient) -> None:
    active = (await client.get("/api/v1/investors", params={"active": "true"})).json()
    inactive = (await client.get("/api/v1/investors", params={"active": "false"})).json()

    assert active["count"] == 18
    assert all(i["active"] for i in active["investors"])
    assert {i["id"] for i in inactive["investors"]} == {"INV-016", "INV-017"}


async def test_list_investors_rejects_invalid_filter(client: AsyncClient) -> None:
    response = await client.get("/api/v1/investors", params={"active": "sometimes"})
    assert response.status_code == 422


async def test_get_investor(client: AsyncClient) -> None:
    response = await client.get("/api/v1/investors/INV-003")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "INV-003"
    assert body["investor_name"] == "Meridale Global Asset Management"
    assert body["preferred_regions"] == ["Global"]
    assert body["risk_tolerance"] == "medium"


async def test_inactive_investor_can_still_be_looked_up(client: AsyncClient) -> None:
    response = await client.get("/api/v1/investors/INV-016")
    assert response.status_code == 200
    assert response.json()["active"] is False


async def test_unknown_investor_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/investors/INV-999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Investor mandate 'INV-999' not found"}
