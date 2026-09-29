"""Health and application-info endpoints."""

from httpx import AsyncClient

from app import __version__


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "finmatch-api"}


async def test_root_returns_application_info(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "FinMatch AI"
    assert body["version"] == __version__
    assert body["docs_url"] == "/docs"
    assert "not affiliated with" in body["disclaimer"]
    assert "synthetic data" in body["disclaimer"]


async def test_openapi_schema_is_served(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/matches" in response.json()["paths"]
