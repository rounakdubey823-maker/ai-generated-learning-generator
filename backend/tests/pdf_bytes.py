"""Helpers that build tiny PDFs in-memory for tests. No network, no disk fixtures."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfWriter


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def text_pdf(text: str = "Photosynthesis converts light into chemical energy.") -> bytes:
    """Minimal valid PDF 1.4 with a single Helvetica text stream."""
    escaped = _escape(text)
    stream = f"BT /F1 12 Tf 50 750 Td ({escaped}) Tj ET".encode("latin-1", "replace")

    def obj(n: int, body: bytes) -> bytes:
        return f"{n} 0 obj\n".encode("ascii") + body + b"\nendobj\n"

    objects = [
        obj(1, b"<< /Type /Catalog /Pages 2 0 R >>"),
        obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
        obj(
            3,
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        ),
        obj(4, b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"),
        obj(5, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    ]
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body = b"".join(objects)
    offsets = []
    cursor = len(header)
    for item in objects:
        offsets.append(cursor)
        cursor += len(item)
    xref = [b"xref\n0 6\n0000000000 65535 f \n"]
    for off in offsets:
        xref.append(f"{off:010d} 00000 n \n".encode("ascii"))
    trailer = (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(cursor).encode("ascii")
        + b"\n%%EOF\n"
    )
    return header + body + b"".join(xref) + trailer


def blank_pdf() -> bytes:
    """Valid PDF with a page but no text (stands in for a scanned image PDF)."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def empty_pages_pdf() -> bytes:
    writer = PdfWriter()
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def encrypted_pdf(password: str = "secret") -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt(password)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def truncated_pdf() -> bytes:
    return b"%PDF-1.4\n1 0 obj << /Type /Catalog >>\n"  # incomplete body
