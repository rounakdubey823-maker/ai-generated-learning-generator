"""
Utility helpers for the AI module.
"""

from __future__ import annotations

import re


def sanitise_topic(topic: str) -> str:
    """Strip control characters and normalise whitespace in a topic string."""
    topic = re.sub(r"[\x00-\x1f\x7f]", "", topic)
    return " ".join(topic.split()).strip()


def truncate(text: str, max_chars: int = 4000) -> str:
    """Truncate text to stay within LLM context limits."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


def extract_json_text(raw: str) -> str:
    """Strip optional markdown fences around a JSON payload."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, count=1, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text, count=1)
    return text.strip()


def redact_secrets(message: str, *secrets: str) -> str:
    """Replace configured API keys so they never appear in error payloads."""
    redacted = message
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted
