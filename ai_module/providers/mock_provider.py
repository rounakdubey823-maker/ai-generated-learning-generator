"""
Explicit development mock provider.

IMPORTANT:
- This provider is ONLY activated in development when no real API key is set.
- Every response is clearly marked with  is_mock=True.
- Responses are labelled "[MOCK]" so they can never be mistaken for real AI output.
- This must never be used in production.
"""

from __future__ import annotations

import json

from ai_module.providers.base import BaseProvider


class MockProvider(BaseProvider):
    name    = "mock"
    model   = "mock-v1"
    is_mock = True

    # ── Static mock payloads ───────────────────────────────────────────────────

    _NOTES_PAYLOAD = {
        "title": "[MOCK] Introduction to {topic}",
        "sections": [
            {
                "heading": "[MOCK] What is {topic}?",
                "body": (
                    "This is a mock response for development purposes. "
                    "Configure a real AI provider API key to receive actual content."
                ),
            },
            {
                "heading": "[MOCK] Key Concepts",
                "body": (
                    "Mock key concepts for {topic} at {level} level. "
                    "Set OPENAI_API_KEY or GOOGLE_API_KEY in your .env file."
                ),
            },
            {
                "heading": "[MOCK] Example",
                "body": "This section would contain a real example when a live provider is configured.",
            },
        ],
    }

    _SUMMARY_PAYLOAD = {
        "title": "[MOCK] Summary of {topic}",
        "summary": (
            "This is a mock summary for development purposes. "
            "{topic} is an important subject at the {level} level. "
            "Configure a real AI provider to get a meaningful summary."
        ),
        "key_points": [
            "[MOCK] Key point 1 — configure a real provider for actual content",
            "[MOCK] Key point 2 — set OPENAI_API_KEY or GOOGLE_API_KEY in .env",
            "[MOCK] Key point 3 — this mock is only active in development mode",
        ],
    }

    _QUIZ_PAYLOAD = {
        "title": "[MOCK] Quiz on {topic}",
        "questions": [
            {
                "question": "[MOCK] What does {topic} primarily involve?",
                "options": [
                    {"label": "A", "text": "Mock option A"},
                    {"label": "B", "text": "Mock option B"},
                    {"label": "C", "text": "Mock option C"},
                    {"label": "D", "text": "Mock option D"},
                ],
                "correct_label": "A",
                "explanation": "[MOCK] This explanation would be real with a live AI provider.",
            },
        ]
        * 5,  # repeat to satisfy min 5 questions
    }

    _PAYLOADS = {
        "notes":   _NOTES_PAYLOAD,
        "summary": _SUMMARY_PAYLOAD,
        "quiz":    _QUIZ_PAYLOAD,
    }

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        # Detect content_type from the user prompt keyword
        content_type = "notes"
        for ct in ("notes", "summary", "quiz"):
            if ct in user_prompt.lower() or ct in system_prompt.lower():
                content_type = ct
                break

        # Extract topic + level for template substitution
        topic = "Unknown Topic"
        level = "beginner"
        for line in user_prompt.splitlines():
            if line.startswith("Topic:"):
                topic = line.split(":", 1)[1].strip()
            elif line.startswith("Learning level:"):
                level = line.split(":", 1)[1].strip()

        payload = json.loads(json.dumps(self._PAYLOADS[content_type]))  # deep copy via JSON

        # Fill templates recursively
        payload_str = json.dumps(payload).replace("{topic}", topic).replace("{level}", level)
        return payload_str
