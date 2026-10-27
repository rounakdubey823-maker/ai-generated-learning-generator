"""
Centralised exception classes and FastAPI exception handlers.

All API errors return the same envelope:
  {
    "error": {
      "code":    "SNAKE_CASE_CODE",
      "message": "Human readable message",
      "detail":  <any | null>
    }
  }
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


# ── Custom exception base ──────────────────────────────────────────────────────

class AppError(Exception):
    """Base class for all application-level errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, detail: Optional[Any] = None) -> None:
        self.message = message
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORIZED"


class ServiceUnavailableError(AppError):
    """Raised when a required external service (e.g. AI provider) is not configured."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "SERVICE_UNAVAILABLE"


class PayloadTooLargeError(AppError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    code = "PAYLOAD_TOO_LARGE"


class DocumentError(AppError):
    """Base class for PDF / upload document failures."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "DOCUMENT_ERROR"


class DocumentInvalidTypeError(DocumentError):
    code = "DOCUMENT_INVALID_TYPE"


class DocumentEncryptedError(DocumentError):
    code = "DOCUMENT_ENCRYPTED"


class DocumentEmptyError(DocumentError):
    code = "DOCUMENT_EMPTY"


class DocumentNoTextError(DocumentError):
    code = "DOCUMENT_NO_TEXT"


class DocumentUnreadableError(DocumentError):
    code = "DOCUMENT_UNREADABLE"


# ── Response helpers ───────────────────────────────────────────────────────────

def _error_body(code: str, message: str, detail: Any = None) -> dict:
    return {"error": {"code": code, "message": message, "detail": detail}}


# ── Exception handlers ─────────────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI app instance."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.detail),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(
                f"HTTP_{exc.status_code}",
                str(exc.detail),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Flatten Pydantic v2 errors into a readable list
        errors = [
            {"field": " → ".join(str(loc) for loc in e["loc"]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                "VALIDATION_ERROR",
                "Request body failed validation.",
                errors,
            ),
        )
