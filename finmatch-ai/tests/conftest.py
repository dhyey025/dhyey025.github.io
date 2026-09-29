"""Shared fixtures.

The API is exercised in-process with ``httpx.AsyncClient`` + ``ASGITransport``. The
app's lifespan is entered explicitly so the mandate dataset is loaded exactly as it
is in production.
"""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "investor_mandates.json"


def make_settings(data_path: Path = DATA_PATH) -> Settings:
    # _env_file=None: tests must not depend on a developer's local .env file.
    return Settings(_env_file=None, environment="test", investor_data_path=data_path)


@asynccontextmanager
async def running_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Client for an app backed by the real synthetic dataset."""
    async with running_client(create_app(make_settings())) as http_client:
        yield http_client


@pytest.fixture
def write_dataset(tmp_path: Path) -> Callable[[list[dict[str, Any]]], Path]:
    """Write a custom mandate dataset (same file format as production) and return its path."""

    def _write(mandates: list[dict[str, Any]]) -> Path:
        path = tmp_path / "mandates.json"
        path.write_text(
            json.dumps({"metadata": {"synthetic": True}, "mandates": mandates}),
            encoding="utf-8",
        )
        return path

    return _write
