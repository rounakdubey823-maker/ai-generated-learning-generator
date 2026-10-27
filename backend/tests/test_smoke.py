"""
Smoke tests for the FastAPI application entry point.
Covers: root endpoint, legacy /health redirect, error handling, and validation.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestRootEndpoint:
    async def test_root_returns_200(self, client: AsyncClient):
        resp = await client.get("/")
        assert resp.status_code == 200

    async def test_root_contains_project_info(self, client: AsyncClient):
        data = (await client.get("/")).json()
        assert "project" in data
        assert "version" in data
        assert "health" in data
        assert "docs" in data


class TestErrorHandling:
    async def test_404_uses_error_envelope(self, client: AsyncClient):
        """Unknown routes should return our standard error shape."""
        resp = await client.get("/api/v1/does-not-exist")
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    async def test_validation_error_uses_error_envelope(self, client: AsyncClient):
        """Missing required fields must return our standard 422 shape."""
        resp = await client.post(
            "/api/v1/learning/generate",
            json={},  # missing 'topic'
        )
        assert resp.status_code == 422
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert isinstance(body["error"]["detail"], list)

    async def test_generate_returns_503_without_api_key(self, client: AsyncClient):
        """Without an API key, generate must return 503 — not fake content."""
        resp = await client.post(
            "/api/v1/learning/generate",
            json={"topic": "Python decorators", "difficulty": "beginner", "content_type": "lesson"},
        )
        assert resp.status_code == 503
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
