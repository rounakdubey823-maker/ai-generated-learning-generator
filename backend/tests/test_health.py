"""
Tests for GET /api/v1/health
"""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

BASE = "/api/v1/health"


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    """Grouped tests for the /api/v1/health endpoint."""

    async def test_returns_200(self, client: AsyncClient):
        resp = await client.get(BASE)
        assert resp.status_code == 200, resp.text

    async def test_response_is_json(self, client: AsyncClient):
        resp = await client.get(BASE)
        assert resp.headers["content-type"].startswith("application/json")

    async def test_status_field_is_ok(self, client: AsyncClient):
        """Status must be 'ok' when the DB is reachable (SQLite always is in tests)."""
        data = (await client.get(BASE)).json()
        assert data["status"] == "ok"

    async def test_contains_version(self, client: AsyncClient):
        data = (await client.get(BASE)).json()
        assert "version" in data
        assert isinstance(data["version"], str)

    async def test_contains_environment(self, client: AsyncClient):
        data = (await client.get(BASE)).json()
        assert "environment" in data

    async def test_contains_uptime(self, client: AsyncClient):
        data = (await client.get(BASE)).json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0

    async def test_dependencies_database_ok(self, client: AsyncClient):
        data = (await client.get(BASE)).json()
        assert "dependencies" in data
        assert data["dependencies"]["database"]["status"] == "ok"

    async def test_response_shape(self, client: AsyncClient):
        """Ensure the response has all required top-level keys."""
        data = (await client.get(BASE)).json()
        required_keys = {"status", "version", "environment", "uptime_seconds", "dependencies"}
        assert required_keys.issubset(data.keys())
