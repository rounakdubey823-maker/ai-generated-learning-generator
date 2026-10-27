"""Tests for POST /api/v1/documents/upload."""

from __future__ import annotations

import json
import os
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from tests.pdf_bytes import blank_pdf, empty_pages_pdf, encrypted_pdf, text_pdf, truncated_pdf

BASE = "/api/v1/documents/upload"


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _upload(filename: str, content: bytes, content_type: str = "application/pdf"):
    return {"file": (filename, content, content_type)}


class TestValidPdf:
    async def test_extracts_text(self, client: AsyncClient):
        resp = await client.post(
            BASE, files=_upload("notes.pdf", text_pdf("Newton's laws of motion"))
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "Newton" in data["text"]
        assert data["page_count"] == 1
        assert data["generated"] is None
        assert data["filename"] == "notes.pdf"

    async def test_strips_path_from_filename(self, client: AsyncClient):
        resp = await client.post(
            BASE, files=_upload("../../etc/passwd.pdf", text_pdf("Gravity"))
        )
        assert resp.status_code == 200
        assert resp.json()["filename"] == "passwd.pdf"

    async def test_temp_file_is_removed(self, client: AsyncClient):
        created: list[str] = []
        real_mkstemp = __import__("tempfile").mkstemp

        def spy(*args, **kwargs):
            fd, path = real_mkstemp(*args, **kwargs)
            created.append(path)
            return fd, path

        with patch("app.services.pdf_extractor.tempfile.mkstemp", side_effect=spy):
            resp = await client.post(BASE, files=_upload("ok.pdf", text_pdf("Atoms")))
        assert resp.status_code == 200
        assert created
        assert all(not os.path.exists(p) for p in created)


class TestInvalidPdf:
    async def test_missing_file_returns_422(self, client: AsyncClient):
        resp = await client.post(BASE)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_wrong_extension_rejected(self, client: AsyncClient):
        resp = await client.post(BASE, files=_upload("notes.txt", text_pdf("Hi")))
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "DOCUMENT_INVALID_TYPE"

    async def test_wrong_content_type_rejected(self, client: AsyncClient):
        resp = await client.post(
            BASE, files=_upload("notes.pdf", text_pdf("Hi"), "text/plain")
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "DOCUMENT_INVALID_TYPE"

    async def test_wrong_signature_rejected(self, client: AsyncClient):
        resp = await client.post(
            BASE, files=_upload("notes.pdf", b"\x89PNG\r\n\x1a\nnot-a-pdf")
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "DOCUMENT_INVALID_TYPE"

    async def test_empty_file_rejected(self, client: AsyncClient):
        resp = await client.post(BASE, files=_upload("empty.pdf", b""))
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "DOCUMENT_EMPTY"

    async def test_empty_pages_rejected(self, client: AsyncClient):
        resp = await client.post(BASE, files=_upload("empty.pdf", empty_pages_pdf()))
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] in {"DOCUMENT_EMPTY", "DOCUMENT_UNREADABLE"}

    async def test_scanned_pdf_rejected(self, client: AsyncClient):
        resp = await client.post(BASE, files=_upload("scan.pdf", blank_pdf()))
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "DOCUMENT_NO_TEXT"

    async def test_encrypted_pdf_rejected(self, client: AsyncClient):
        resp = await client.post(BASE, files=_upload("secret.pdf", encrypted_pdf()))
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "DOCUMENT_ENCRYPTED"

    async def test_unreadable_pdf_rejected(self, client: AsyncClient):
        resp = await client.post(BASE, files=_upload("broken.pdf", truncated_pdf()))
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] in {
            "DOCUMENT_UNREADABLE",
            "DOCUMENT_EMPTY",
            "DOCUMENT_NO_TEXT",
        }

    async def test_too_large_rejected(self, client: AsyncClient):
        with patch("app.api.v1.endpoints.documents.settings.MAX_UPLOAD_BYTES", 20):
            with patch("app.services.pdf_extractor.settings.MAX_UPLOAD_BYTES", 20):
                resp = await client.post(
                    BASE, files=_upload("big.pdf", text_pdf("x" * 200))
                )
        assert resp.status_code == 413
        assert resp.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

    async def test_content_length_rejected_before_read(self, client: AsyncClient):
        with patch("app.api.v1.endpoints.documents.settings.MAX_UPLOAD_BYTES", 10):
            with patch("app.api.v1.endpoints.documents._MULTIPART_OVERHEAD", 0):
                resp = await client.post(
                    BASE,
                    files=_upload("big.pdf", text_pdf("enough bytes to exceed ten")),
                )
        assert resp.status_code == 413
        assert resp.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


class TestGenerateFromUpload:
    @patch("ai_module.generator._build_provider")
    async def test_generate_true_calls_ai_service(self, mock_build, client: AsyncClient):
        from ai_module.providers.openai_provider import OpenAIProvider

        notes = {
            "title": "From PDF",
            "sections": [{"heading": "One", "body": "Grounded in the document."}],
        }
        p = AsyncMock(spec=OpenAIProvider)
        p.name = "openai"
        p.model = "gpt-4o-mini"
        p.is_mock = False
        p.generate = AsyncMock(return_value=json.dumps(notes))
        mock_build.return_value = p

        resp = await client.post(
            BASE,
            files=_upload("newton.pdf", text_pdf("Newton's first law")),
            data={
                "generate": "true",
                "content_type": "notes",
                "learning_level": "beginner",
                "language": "English",
                "topic": "Newton",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["generated"] is not None
        assert data["generated"]["is_mock"] is False
        assert data["generated"]["content"]["title"] == "From PDF"
        p.generate.assert_awaited()
        user_prompt = p.generate.await_args.args[1]
        assert "Newton" in user_prompt
        assert "first law" in user_prompt or "source document" in user_prompt.lower()

    async def test_generate_false_does_not_include_generated(self, client: AsyncClient):
        resp = await client.post(
            BASE,
            files=_upload("notes.pdf", text_pdf("Cells")),
            data={"generate": "false"},
        )
        assert resp.status_code == 200
        assert resp.json()["generated"] is None


class TestExtractorCleanupOnError:
    def test_temp_removed_when_extraction_fails(self):
        from app.services.pdf_extractor import extract_from_upload

        created: list[str] = []
        real_mkstemp = __import__("tempfile").mkstemp

        def spy(*args, **kwargs):
            fd, path = real_mkstemp(*args, **kwargs)
            created.append(path)
            return fd, path

        with patch("app.services.pdf_extractor.tempfile.mkstemp", side_effect=spy):
            with pytest.raises(Exception):
                extract_from_upload(
                    BytesIO(truncated_pdf()),
                    filename="broken.pdf",
                    content_type="application/pdf",
                )
        assert created
        assert all(not os.path.exists(p) for p in created)
