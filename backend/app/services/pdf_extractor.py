"""
Safe PDF text extraction.

This module only *parses* PDF objects with pypdf. It never shells out,
never evaluates JavaScript, and never opens uploaded bytes as executable.
Temporary copies are always deleted in a finally block.
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError, PdfStreamError

from app.core.config import settings
from app.core.errors import (
    DocumentEmptyError,
    DocumentEncryptedError,
    DocumentInvalidTypeError,
    DocumentNoTextError,
    DocumentUnreadableError,
    PayloadTooLargeError,
)

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF-"
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/octet-stream",
}
READ_CHUNK = 64 * 1024


@dataclass(frozen=True)
class ExtractedPdf:
    filename: str
    page_count: int
    text: str
    truncated: bool


def sanitise_filename(filename: str | None) -> str:
    raw = (filename or "upload.pdf").replace("\\", "/")
    name = Path(raw).name.strip() or "upload.pdf"
    return name


def _validate_name_and_type(filename: str, content_type: str | None) -> None:
    if not filename.lower().endswith(".pdf"):
        raise DocumentInvalidTypeError(
            message="Only PDF files are accepted. Rename the file with a .pdf extension.",
            detail={"filename": filename},
        )
    if content_type:
        mime = content_type.split(";")[0].strip().lower()
        if mime and mime not in ALLOWED_CONTENT_TYPES:
            raise DocumentInvalidTypeError(
                message=f"Unsupported content type {mime!r}. Upload an application/pdf file.",
                detail={"content_type": mime},
            )


def _validate_signature(header: bytes) -> None:
    if not header.startswith(PDF_MAGIC):
        raise DocumentInvalidTypeError(
            message="File signature is not a PDF. The upload was rejected.",
            detail={"expected_magic": "%PDF-"},
        )


def _write_upload_to_temp(
    source: BinaryIO,
    header: bytes,
    max_bytes: int,
) -> str:
    fd, path = tempfile.mkstemp(prefix="ai_upload_", suffix=".pdf")
    total = 0
    try:
        with os.fdopen(fd, "wb") as dest:
            dest.write(header)
            total += len(header)
            if total > max_bytes:
                raise PayloadTooLargeError(
                    message=f"File exceeds the maximum upload size of {max_bytes} bytes.",
                    detail={"max_upload_bytes": max_bytes},
                )
            while True:
                chunk = source.read(READ_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise PayloadTooLargeError(
                        message=f"File exceeds the maximum upload size of {max_bytes} bytes.",
                        detail={"max_upload_bytes": max_bytes, "bytes_read": total},
                    )
                dest.write(chunk)
        return path
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        Path(path).unlink(missing_ok=True)
        raise


def extract_text_from_path(path: str, *, max_pages: int, max_chars: int) -> tuple[str, int, bool]:
    """
    Parse a PDF on disk and return (text, page_count, truncated).

    Raises Document* errors for encrypted, empty, scanned, or corrupt files.
    """
    try:
        reader = PdfReader(path, strict=False)
    except (PdfReadError, PdfStreamError, ValueError, OSError) as exc:
        raise DocumentUnreadableError(
            message="The PDF could not be read. The file may be corrupt or truncated.",
            detail={"reason": str(exc)},
        ) from exc

    if getattr(reader, "is_encrypted", False):
        decrypted = False
        try:
            decrypted = bool(reader.decrypt(""))
        except (FileNotDecryptedError, PdfReadError, NotImplementedError, ValueError) as exc:
            raise DocumentEncryptedError(
                message="This PDF is encrypted or password-protected. Upload an unlocked copy.",
                detail={"reason": str(exc)},
            ) from exc
        if not decrypted:
            raise DocumentEncryptedError(
                message="This PDF is encrypted or password-protected. Upload an unlocked copy.",
            )

    pages = list(reader.pages)
    if not pages:
        raise DocumentEmptyError(
            message="The PDF has no pages.",
        )
    if len(pages) > max_pages:
        raise DocumentUnreadableError(
            message=f"The PDF has {len(pages)} pages; the maximum allowed is {max_pages}.",
            detail={"page_count": len(pages), "max_pdf_pages": max_pages},
        )

    chunks: list[str] = []
    try:
        for page in pages:
            chunks.append(page.extract_text() or "")
    except FileNotDecryptedError as exc:
        raise DocumentEncryptedError(
            message="This PDF is encrypted or password-protected. Upload an unlocked copy.",
        ) from exc
    except Exception as exc:
        raise DocumentUnreadableError(
            message="Text could not be extracted from this PDF.",
            detail={"reason": str(exc)},
        ) from exc

    text = "\n".join(chunks)
    text = " ".join(text.split()).strip()
    if not text:
        raise DocumentNoTextError(
            message=(
                "No extractable text was found. This is usually a scanned or image-only PDF. "
                "Upload a text-based PDF, or OCR it first."
            ),
            detail={"page_count": len(pages)},
        )

    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"
    return text, len(pages), truncated


def extract_from_upload(
    file_obj: BinaryIO,
    *,
    filename: str | None,
    content_type: str | None,
    max_bytes: int | None = None,
    max_pages: int | None = None,
    max_chars: int | None = None,
) -> ExtractedPdf:
    """
    Validate, spool to a temp file, extract text, then always delete the temp file.
    """
    max_bytes = max_bytes if max_bytes is not None else settings.MAX_UPLOAD_BYTES
    max_pages = max_pages if max_pages is not None else settings.MAX_PDF_PAGES
    max_chars = max_chars if max_chars is not None else settings.MAX_EXTRACTED_CHARS

    safe_name = sanitise_filename(filename)
    _validate_name_and_type(safe_name, content_type)

    header = file_obj.read(len(PDF_MAGIC) + 8)
    if not header:
        raise DocumentEmptyError(message="The uploaded file is empty.")
    _validate_signature(header)

    temp_path: str | None = None
    try:
        temp_path = _write_upload_to_temp(file_obj, header, max_bytes)
        text, page_count, truncated = extract_text_from_path(
            temp_path, max_pages=max_pages, max_chars=max_chars
        )
        return ExtractedPdf(
            filename=safe_name,
            page_count=page_count,
            text=text,
            truncated=truncated,
        )
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)
            logger.debug("Removed temporary upload %s", temp_path)
