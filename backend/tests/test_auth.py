"""
Tests for Authentication and User Database Operations:
- POST /api/v1/auth/register
- POST /api/v1/auth/login
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import init_db
from main import app


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestUserRegistration:
    async def test_register_success(self, client: AsyncClient):
        email = f"user_{uuid.uuid4().hex[:8]}@example.com"
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecretPassword123!", "full_name": "Test User"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == email
        assert data["full_name"] == "Test User"
        assert "id" in data
        assert data["is_active"] is True
        assert "password" not in data
        assert "hashed_password" not in data

    async def test_register_duplicate_email(self, client: AsyncClient):
        email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
        # First registration
        resp1 = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password123!"},
        )
        assert resp1.status_code == 201

        # Second registration with same email
        resp2 = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password123!"},
        )
        assert resp2.status_code == 400
        data = resp2.json()
        assert "error" in data
        assert "already registered" in data["error"]["message"].lower()

    async def test_register_invalid_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "Password123!"},
        )
        assert resp.status_code == 422


class TestUserLogin:
    async def test_login_success(self, client: AsyncClient):
        email = f"login_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePassword456!"
        # Create user
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Login User"},
        )
        assert reg_resp.status_code == 201

        # Login with OAuth2 form data
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        assert login_resp.status_code == 200
        token_data = login_resp.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert len(token_data["access_token"]) > 20

    async def test_login_wrong_password(self, client: AsyncClient):
        email = f"login_{uuid.uuid4().hex[:8]}@example.com"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "CorrectPassword123!"},
        )

        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "WrongPassword123!"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert "error" in data
        assert "incorrect" in data["error"]["message"].lower()

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "nobody_exists@example.com", "password": "SomePassword123!"},
        )
        assert resp.status_code == 401
