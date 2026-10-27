"""
Prompt engineering for the AI learning generator.

Every content type has:
  - A SYSTEM prompt (instructs the LLM on role, JSON-only output, schema)
  - A USER prompt builder (fills in topic / level / language)

The system prompts embed the exact JSON schema the LLM must return.
Providers should pass the system prompt as the system/developer message
and the user prompt as the human turn.
"""

from __future__ import annotations

from typing import Optional

from ai_module.utils import truncate

# ── Notes prompts ──────────────────────────────────────────────────────────────

NOTES_SYSTEM = """
You are an expert educator who creates clear, well-structured study notes.
You MUST respond with ONLY a valid JSON object — no markdown fences, no prose.

The JSON must match this exact schema:
{
  "title": "<concise title for the topic>",
  "sections": [
    {
      "heading": "<section heading>",
      "body":    "<detailed explanation, 2-5 sentences>"
    }
  ]
}

Rules:
- Include 3 to 6 sections covering the topic thoroughly.
- Use the specified language for all text values.
- Adapt vocabulary and depth to the specified learning level.
- Do NOT include any text outside the JSON object.
""".strip()


def notes_user_prompt(topic: str, level: str, language: str) -> str:
    return (
        f"Topic: {topic}\n"
        f"Learning level: {level}\n"
        f"Language: {language}\n"
        f"Content type: notes\n\n"
        "Generate the JSON study notes now."
    )


# ── Summary prompts ────────────────────────────────────────────────────────────

SUMMARY_SYSTEM = """
You are an expert educator who creates concise topic summaries.
You MUST respond with ONLY a valid JSON object — no markdown fences, no prose.

The JSON must match this exact schema:
{
  "title":      "<concise title>",
  "summary":    "<3-5 sentence paragraph summarising the topic>",
  "key_points": ["<key point 1>", "<key point 2>", "<key point 3>"]
}

Rules:
- Provide 3 to 7 key points as short, memorable statements.
- Use the specified language for all text values.
- Adapt vocabulary and depth to the specified learning level.
- Do NOT include any text outside the JSON object.
""".strip()


def summary_user_prompt(topic: str, level: str, language: str) -> str:
    return (
        f"Topic: {topic}\n"
        f"Learning level: {level}\n"
        f"Language: {language}\n"
        f"Content type: summary\n\n"
        "Generate the JSON summary now."
    )


# ── Quiz prompts ───────────────────────────────────────────────────────────────

QUIZ_SYSTEM = """
You are an expert educator who creates multiple-choice quizzes.
You MUST respond with ONLY a valid JSON object — no markdown fences, no prose.

The JSON must match this exact schema:
{
  "title": "<quiz title>",
  "questions": [
    {
      "question":      "<the question text>",
      "options": [
        {"label": "A", "text": "<option text>"},
        {"label": "B", "text": "<option text>"},
        {"label": "C", "text": "<option text>"},
        {"label": "D", "text": "<option text>"}
      ],
      "correct_label": "A",
      "explanation":   "<why the correct answer is right>"
    }
  ]
}

Rules:
- Generate exactly 5 questions.
- Every question must have exactly 4 options labelled A, B, C, D.
- correct_label must be one of "A", "B", "C", "D".
- Use the specified language for all text values.
- Adapt difficulty to the specified learning level.
- Do NOT include any text outside the JSON object.
""".strip()


def quiz_user_prompt(topic: str, level: str, language: str) -> str:
    return (
        f"Topic: {topic}\n"
        f"Learning level: {level}\n"
        f"Language: {language}\n"
        f"Content type: quiz\n\n"
        "Generate the JSON quiz now."
    )


# ── Dispatcher ────────────────────────────────────────────────────────────────

_SYSTEM_PROMPTS = {
    "notes":   NOTES_SYSTEM,
    "summary": SUMMARY_SYSTEM,
    "quiz":    QUIZ_SYSTEM,
}

_USER_PROMPT_BUILDERS = {
    "notes":   notes_user_prompt,
    "summary": summary_user_prompt,
    "quiz":    quiz_user_prompt,
}


def get_prompts(
    topic: str,
    learning_level: str,
    language: str,
    content_type: str,
    source_text: Optional[str] = None,
) -> tuple[str, str]:
    """
    Return (system_prompt, user_prompt) for the given content type.

    Raises:
        ValueError: if content_type is not recognised.
    """
    if content_type not in _SYSTEM_PROMPTS:
        raise ValueError(f"Unknown content_type: {content_type!r}")
    system = _SYSTEM_PROMPTS[content_type]
    user   = _USER_PROMPT_BUILDERS[content_type](topic, learning_level, language)
    if source_text:
        user += (
            "\n\nUse the following source document as the primary material. "
            "Do not invent facts that contradict it.\n---\n"
            f"{truncate(source_text, 12_000)}\n---\n"
        )
    return system, user
