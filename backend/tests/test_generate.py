"""
Tests for POST /api/v1/generate

Strategy:
- All tests mock the provider at the BaseProvider.generate() level so no real
  API calls are made.
- Tests verify request validation, response shape, is_mock flag, provider error
  propagation, timeout handling, and the 503 when no provider is configured.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

BASE = "/api/v1/generate"


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _notes_payload(topic: str = "Python decorators") -> dict:
    return {
        "title": f"Introduction to {topic}",
        "sections": [
            {"heading": "What it is", "body": "A decorator wraps a function."},
            {"heading": "Example",    "body": "Use @functools.wraps to preserve metadata."},
        ],
    }


def _summary_payload(topic: str = "Recursion") -> dict:
    return {
        "title":      f"Summary of {topic}",
        "summary":    "Recursion is a technique where a function calls itself.",
        "key_points": ["Base case required", "Reduces problem size", "Stack memory used"],
    }


def _quiz_payload(topic: str = "Big O notation") -> dict:
    question = {
        "question":      f"What is the time complexity of binary search on {topic}?",
        "options": [
            {"label": "A", "text": "O(n)"},
            {"label": "B", "text": "O(log n)"},
            {"label": "C", "text": "O(n²)"},
            {"label": "D", "text": "O(1)"},
        ],
        "correct_label": "B",
        "explanation":   "Binary search halves the search space each step.",
    }
    return {"title": f"Quiz on {topic}", "questions": [question] * 5}


def _mock_provider(raw_payload: Any, *, provider_name: str = "openai", model: str = "gpt-4o-mini"):
    """Return a patched provider that yields the given payload as JSON."""
    mock = AsyncMock(return_value=json.dumps(raw_payload))
    return mock


# ── Happy-path tests ───────────────────────────────────────────────────────────

class TestGenerateNotes:
    @patch("ai_module.generator._build_provider")
    async def test_notes_returns_200(self, mock_build, client: AsyncClient):
        from ai_module.providers.openai_provider import OpenAIProvider
        p = AsyncMock(spec=OpenAIProvider)
        p.name    = "openai"
        p.model   = "gpt-4o-mini"
        p.is_mock = False
        p.generate = AsyncMock(return_value=json.dumps(_notes_payload()))
        mock_build.return_value = p

        resp = await client.post(
            BASE,
            json={"topic": "Python decorators", "learning_level": "beginner",
                  "language": "English", "content_type": "notes"},
        )
        assert resp.status_code == 200, resp.text

    @patch("ai_module.generator._build_provider")
    async def test_notes_response_shape(self, mock_build, client: AsyncClient):
        from ai_module.providers.openai_provider import OpenAIProvider
        p = AsyncMock(spec=OpenAIProvider)
        p.name    = "openai"
        p.model   = "gpt-4o-mini"
        p.is_mock = False
        p.generate = AsyncMock(return_value=json.dumps(_notes_payload()))
        mock_build.return_value = p

        data = (await client.post(BASE, json={
            "topic": "Python decorators", "content_type": "notes"
        })).json()

        required = {"id", "topic", "learning_level", "language", "content_type",
                    "content", "provider", "model", "is_mock", "generated_at"}
        assert required.issubset(data.keys())

    @patch("ai_module.generator._build_provider")
    async def test_notes_content_has_sections(self, mock_build, client: AsyncClient):
        from ai_module.providers.openai_provider import OpenAIProvider
        p = AsyncMock(spec=OpenAIProvider)
        p.name = "openai"; p.model = "gpt-4o-mini"; p.is_mock = False
        p.generate = AsyncMock(return_value=json.dumps(_notes_payload()))
        mock_build.return_value = p

        data = (await client.post(BASE, json={
            "topic": "Python decorators", "content_type": "notes"
        })).json()
        assert "sections" in data["content"]
        assert isinstance(data["content"]["sections"], list)
        assert len(data["content"]["sections"]) > 0

    @patch("ai_module.generator._build_provider")
    async def test_is_mock_false_for_real_provider(self, mock_build, client: AsyncClient):
        from ai_module.providers.openai_provider import OpenAIProvider
        p = AsyncMock(spec=OpenAIProvider)
        p.name = "openai"; p.model = "gpt-4o-mini"; p.is_mock = False
        p.generate = AsyncMock(return_value=json.dumps(_notes_payload()))
        mock_build.return_value = p

        data = (await client.post(BASE, json={
            "topic": "Python decorators", "content_type": "notes"
        })).json()
        assert data["is_mock"] is False


class TestGenerateSummary:
    @patch("ai_module.generator._build_provider")
    async def test_summary_returns_200(self, mock_build, client: AsyncClient):
        from ai_module.providers.openai_provider import OpenAIProvider
        p = AsyncMock(spec=OpenAIProvider)
        p.name = "openai"; p.model = "gpt-4o-mini"; p.is_mock = False
        p.generate = AsyncMock(return_value=json.dumps(_summary_payload()))
        mock_build.return_value = p

        resp = await client.post(BASE, json={"topic": "Recursion", "content_type": "summary"})
        assert resp.status_code == 200

    @patch("ai_module.generator._build_provider")
    async def test_summary_has_key_points(self, mock_build, client: AsyncClient):
        from ai_module.providers.openai_provider import OpenAIProvider
        p = AsyncMock(spec=OpenAIProvider)
        p.name = "openai"; p.model = "gpt-4o-mini"; p.is_mock = False
        p.generate = AsyncMock(return_value=json.dumps(_summary_payload()))
        mock_build.return_value = p

        data = (await client.post(BASE, json={"topic": "Recursion", "content_type": "summary"})).json()
        assert "key_points" in data["content"]
        assert len(data["content"]["key_points"]) >= 1


class TestGenerateQuiz:
    @patch("ai_module.generator._build_provider")
    async def test_quiz_returns_200(self, mock_build, client: AsyncClient):
        from ai_module.providers.openai_provider import OpenAIProvider
        p = AsyncMock(spec=OpenAIProvider)
        p.name = "openai"; p.model = "gpt-4o-mini"; p.is_mock = False
        p.generate = AsyncMock(return_value=json.dumps(_quiz_payload()))
        mock_build.return_value = p

        resp = await client.post(BASE, json={"topic": "Big O notation", "content_type": "quiz"})
        assert resp.status_code == 200

    @patch("ai_module.generator._build_provider")
    async def test_quiz_has_questions(self, mock_build, client: AsyncClient):
        from ai_module.providers.openai_provider import OpenAIProvider
        p = AsyncMock(spec=OpenAIProvider)
        p.name = "openai"; p.model = "gpt-4o-mini"; p.is_mock = False
        p.generate = AsyncMock(return_value=json.dumps(_quiz_payload()))
        mock_build.return_value = p

        data = (await client.post(BASE, json={"topic": "Big O notation", "content_type": "quiz"})).json()
        assert "questions" in data["content"]
        assert len(data["content"]["questions"]) == 5

    @patch("ai_module.generator._build_provider")
    async def test_quiz_question_has_options(self, mock_build, client: AsyncClient):
        from ai_module.providers.openai_provider import OpenAIProvider
        p = AsyncMock(spec=OpenAIProvider)
        p.name = "openai"; p.model = "gpt-4o-mini"; p.is_mock = False
        p.generate = AsyncMock(return_value=json.dumps(_quiz_payload()))
        mock_build.return_value = p

        data = (await client.post(BASE, json={"topic": "Big O notation", "content_type": "quiz"})).json()
        q = data["content"]["questions"][0]
        assert "options" in q
        assert len(q["options"]) == 4
        assert "correct_label" in q
        assert "explanation" in q


# ── Validation tests ───────────────────────────────────────────────────────────

class TestRequestValidation:
    async def test_missing_topic_returns_422(self, client: AsyncClient):
        resp = await client.post(BASE, json={"content_type": "notes"})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    async def test_empty_topic_returns_422(self, client: AsyncClient):
        resp = await client.post(BASE, json={"topic": "", "content_type": "notes"})
        assert resp.status_code == 422

    async def test_invalid_learning_level_returns_422(self, client: AsyncClient):
        resp = await client.post(BASE, json={"topic": "AI", "learning_level": "expert"})
        assert resp.status_code == 422

    async def test_invalid_content_type_returns_422(self, client: AsyncClient):
        resp = await client.post(BASE, json={"topic": "AI", "content_type": "lesson"})
        assert resp.status_code == 422

    async def test_all_valid_enum_levels_accepted(self, client: AsyncClient):
        """Enum values should parse correctly — 422 would be a regression."""
        for level in ("beginner", "intermediate", "advanced"):
            with patch("ai_module.generator._build_provider") as mb:
                from ai_module.providers.openai_provider import OpenAIProvider
                p = AsyncMock(spec=OpenAIProvider)
                p.name = "openai"; p.model = "gpt-4o-mini"; p.is_mock = False
                p.generate = AsyncMock(return_value=json.dumps(_notes_payload()))
                mb.return_value = p
                resp = await client.post(BASE, json={"topic": "AI", "learning_level": level})
                assert resp.status_code == 200, f"level={level} gave {resp.status_code}"


# ── Error handling tests ───────────────────────────────────────────────────────

class TestErrorHandling:
    @patch("ai_module.generator._build_provider")
    async def test_provider_error_returns_503(self, mock_build, client: AsyncClient):
        from ai_module.providers.base import ProviderError
        from ai_module.providers.openai_provider import OpenAIProvider
        p = AsyncMock(spec=OpenAIProvider)
        p.name = "openai"; p.model = "gpt-4o-mini"; p.is_mock = False
        p.generate = AsyncMock(side_effect=ProviderError("API error", provider="openai"))
        mock_build.return_value = p

        resp = await client.post(BASE, json={"topic": "AI", "content_type": "notes"})
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "SERVICE_UNAVAILABLE"

    @patch("ai_module.generator._build_provider")
    async def test_invalid_json_from_provider_returns_503(self, mock_build, client: AsyncClient):
        from ai_module.providers.openai_provider import OpenAIProvider
        p = AsyncMock(spec=OpenAIProvider)
        p.name = "openai"; p.model = "gpt-4o-mini"; p.is_mock = False
        p.generate = AsyncMock(return_value="this is not JSON {{{")
        mock_build.return_value = p

        resp = await client.post(BASE, json={"topic": "AI", "content_type": "notes"})
        assert resp.status_code == 503

    @patch("ai_module.generator._build_provider")
    async def test_wrong_schema_from_provider_returns_503(self, mock_build, client: AsyncClient):
        """Provider returns valid JSON but wrong shape for the content type."""
        from ai_module.providers.openai_provider import OpenAIProvider
        p = AsyncMock(spec=OpenAIProvider)
        p.name = "openai"; p.model = "gpt-4o-mini"; p.is_mock = False
        # Notes schema requires 'sections'; this is missing it
        p.generate = AsyncMock(return_value=json.dumps({"title": "Oops", "wrong_key": []}))
        mock_build.return_value = p

        resp = await client.post(BASE, json={"topic": "AI", "content_type": "notes"})
        assert resp.status_code == 503

    @patch("ai_module.generator._build_provider")
    async def test_no_provider_returns_503(self, mock_build, client: AsyncClient):
        """When _build_provider returns None, expect 503."""
        mock_build.return_value = None  # simulates production with no key

        resp = await client.post(BASE, json={"topic": "AI", "content_type": "notes"})
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert "OPENAI_API_KEY" in resp.json()["error"]["message"]

    @patch("ai_module.generator._build_provider")
    async def test_timeout_returns_503(self, mock_build, client: AsyncClient):
        from ai_module.providers.openai_provider import OpenAIProvider
        from app.core.config import settings

        p = AsyncMock(spec=OpenAIProvider)
        p.name = "openai"
        p.model = "gpt-4o-mini"
        p.is_mock = False

        async def _slow(_system: str, _user: str) -> str:
            await asyncio.sleep(2)
            return json.dumps(_notes_payload())

        p.generate = _slow
        mock_build.return_value = p

        with patch.object(settings, "AI_TIMEOUT_SECONDS", 0.05):
            resp = await client.post(BASE, json={"topic": "AI", "content_type": "notes"})

        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "SERVICE_UNAVAILABLE"

    @patch("ai_module.generator._build_provider")
    async def test_error_payload_does_not_include_api_keys(
        self, mock_build, client: AsyncClient
    ):
        from ai_module.providers.base import ProviderError
        from ai_module.providers.openai_provider import OpenAIProvider

        p = AsyncMock(spec=OpenAIProvider)
        p.name = "openai"
        p.model = "gpt-4o-mini"
        p.is_mock = False
        p.generate = AsyncMock(
            side_effect=ProviderError("API error", provider="openai")
        )
        mock_build.return_value = p

        resp = await client.post(BASE, json={"topic": "AI", "content_type": "notes"})
        body = json.dumps(resp.json())
        assert "sk-" not in body
        assert "AIza" not in body
        assert "OPENAI_API_KEY=" not in body


# ── Mock provider tests ────────────────────────────────────────────────────────

class TestMockProvider:
    async def test_mock_provider_is_labelled(self, client: AsyncClient):
        """In dev with MOCK_AI_IN_DEV=True and no key, response must have is_mock=True."""
        # MockProvider is used by default when no API keys are set (dev env)
        resp = await client.post(BASE, json={"topic": "Sorting algorithms", "content_type": "notes"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_mock"] is True
        assert data["provider"] == "mock"

    async def test_mock_notes_content_contains_mock_label(self, client: AsyncClient):
        resp = await client.post(BASE, json={"topic": "Sorting algorithms", "content_type": "notes"})
        data = resp.json()
        content_str = json.dumps(data["content"])
        assert "[MOCK]" in content_str

    async def test_mock_summary_is_labelled(self, client: AsyncClient):
        resp = await client.post(BASE, json={"topic": "Recursion", "content_type": "summary"})
        assert resp.status_code == 200
        assert resp.json()["is_mock"] is True

    async def test_mock_quiz_is_labelled(self, client: AsyncClient):
        resp = await client.post(BASE, json={"topic": "Binary trees", "content_type": "quiz"})
        assert resp.status_code == 200
        assert resp.json()["is_mock"] is True
