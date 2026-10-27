# API Reference

Base URL: `http://localhost:8000/api/v1`

## Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Root health check |
| GET | `/health` | Liveness probe |

## Auth

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | `{email, password, full_name?}` | Create a new user |
| POST | `/auth/login` | OAuth2 form (`username`, `password`) | Returns JWT token |

## Generate (core)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/generate` | No | Generate notes, a summary, or a quiz |

### POST `/generate` — Request Body

```json
{
  "topic": "Python decorators",
  "learning_level": "beginner",
  "language": "English",
  "content_type": "notes"
}
```

- `topic`: 2–500 characters
- `learning_level`: `beginner` | `intermediate` | `advanced` (default `beginner`)
- `language`: response language (default `English`)
- `content_type`: `notes` | `summary` | `quiz` (default `notes`)

### Response

```json
{
  "id": "uuid",
  "topic": "Python decorators",
  "learning_level": "beginner",
  "language": "English",
  "content_type": "notes",
  "content": {},
  "provider": "openai",
  "model": "gpt-4o-mini",
  "is_mock": false,
  "generated_at": "2026-10-27T13:00:00+00:00"
}
```

`is_mock: true` means a labelled development placeholder was used. It is not real AI output.

Missing API keys in production (or when `MOCK_AI_IN_DEV=false`) return `503` with `SERVICE_UNAVAILABLE`.

## Documents

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/documents/upload` | No | Upload a PDF, extract text, optionally generate learning content |

### POST `/documents/upload`

`multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | PDF file | Yes | Must be `.pdf` and start with the `%PDF-` signature |
| `generate` | bool | No | Default `false`. If `true`, send extracted text to `ai_module` generation |
| `topic` | string | No | Topic for generation (defaults to the filename) |
| `learning_level` | string | No | `beginner` \| `intermediate` \| `advanced` |
| `language` | string | No | Default `English` |
| `content_type` | string | No | `notes` \| `summary` \| `quiz` |

Size and page limits come from env: `MAX_UPLOAD_BYTES` (default 10 MB), `MAX_PDF_PAGES` (50), `MAX_EXTRACTED_CHARS` (20 000).

Uploaded bytes are **parsed only** (pypdf). They are never executed. The server copy is deleted after extraction.

```bash
# Extract text only
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@./lecture.pdf;type=application/pdf"

# Extract text and generate notes from it
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@./lecture.pdf;type=application/pdf" \
  -F "generate=true" \
  -F "content_type=notes" \
  -F "learning_level=beginner" \
  -F "language=English" \
  -F "topic=Lecture notes"
```

### Success response

```json
{
  "id": "uuid",
  "filename": "lecture.pdf",
  "page_count": 3,
  "char_count": 1840,
  "truncated": false,
  "text": "extracted plain text…",
  "generated": null,
  "extracted_at": "2026-10-27T13:00:00+00:00"
}
```

When `generate=true`, `generated` is the same JSON shape as `POST /generate` (`content`, `provider`, `model`, `is_mock`, …).

### Error codes

| HTTP | `error.code` | When |
|------|----------------|------|
| 413 | `PAYLOAD_TOO_LARGE` | File bigger than `MAX_UPLOAD_BYTES` |
| 422 | `DOCUMENT_INVALID_TYPE` | Wrong extension, MIME type, or file signature |
| 422 | `DOCUMENT_EMPTY` | Empty file or PDF with no pages |
| 422 | `DOCUMENT_ENCRYPTED` | Password-protected PDF |
| 422 | `DOCUMENT_NO_TEXT` | Scanned / image-only PDF (no extractable text) |
| 422 | `DOCUMENT_UNREADABLE` | Corrupt PDF or too many pages |
| 503 | `SERVICE_UNAVAILABLE` | `generate=true` but the AI provider failed or is not configured |

## Learning Content (legacy)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/learning/generate` | Optional | Generate AI content |
| GET | `/learning/{id}` | No | Retrieve saved content by ID |

### POST `/learning/generate` — Request Body

```json
{
  "topic": "Python decorators",
  "difficulty": "beginner",
  "content_type": "lesson"
}
```

- `difficulty`: `beginner` | `intermediate` | `advanced`
- `content_type`: `lesson` | `quiz` | `summary`

### Response

```json
{
  "id": "uuid",
  "topic": "Python decorators",
  "difficulty": "beginner",
  "content_type": "lesson",
  "content": "...",
  "ai_provider": "openai",
  "ai_model": "gpt-4o-mini"
}
```

## Adaptive Learning & Progression

All adaptive endpoints use the prefix `/adaptive`. Authentication is supported via `Authorization: Bearer <token>` or works automatically in demo/guest mode.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/adaptive/profile` | Retrieve student profile, current proficiency level, and score stats |
| POST | `/adaptive/session` | Start an adaptive session (`topic`, optional `difficulty`). Returns lesson + quiz with answer keys stripped |
| GET | `/adaptive/session/{id}` | Get session details |
| POST | `/adaptive/session/{id}/quiz/submit` | Submit answers, evaluate against server key, recalculate score, and advance level |
| GET | `/adaptive/progress` | Get student quiz attempt history and level progression |

### 1. POST `/adaptive/session` — Start Adaptive Session

#### Request Body
```json
{
  "topic": "Python Generators and Iterators",
  "difficulty": "beginner",
  "language": "English"
}
```
* `topic` (string, required): 2-500 characters.
* `difficulty` (string, optional): `"beginner"` | `"intermediate"` | `"advanced"`. If omitted, defaults to student's current level.
* `language` (string, optional): default `"English"`.

#### Response (HTTP 201)
```json
{
  "session_id": "56f31b2e-7bd8-4c64-94b8-412b0677b87b",
  "topic": "Python Generators and Iterators",
  "difficulty": "beginner",
  "language": "English",
  "lesson": {
    "title": "Introduction to Python Generators",
    "sections": [
      {
        "heading": "What is a Generator?",
        "body": "A generator is a function that produces a sequence of results using yield."
      }
    ]
  },
  "quiz": [
    {
      "index": 0,
      "question": "Which keyword is used to yield values in a Python generator?",
      "options": [
        {"label": "A", "text": "yield"},
        {"label": "B", "text": "return"},
        {"label": "C", "text": "generate"},
        {"label": "D", "text": "emit"}
      ]
    }
  ],
  "is_completed": false
}
```
*(Notice: `correct_label` and `explanation` are deliberately withheld by the server to prevent cheating).*

### 2. POST `/adaptive/session/{session_id}/quiz/submit` — Submit Quiz

#### Request Body
```json
{
  "answers": [
    {"question_index": 0, "selected_label": "A"},
    {"question_index": 1, "selected_label": "B"},
    {"question_index": 2, "selected_label": "C"},
    {"question_index": 3, "selected_label": "D"},
    {"question_index": 4, "selected_label": "A"}
  ]
}
```

#### Response (HTTP 200)
```json
{
  "session_id": "56f31b2e-7bd8-4c64-94b8-412b0677b87b",
  "total_questions": 5,
  "correct_count": 5,
  "score_percentage": 100.0,
  "previous_level": "beginner",
  "new_level": "intermediate",
  "level_changed": true,
  "details": [
    {
      "question_index": 0,
      "question": "Which keyword is used to yield values in a Python generator?",
      "selected_label": "A",
      "correct_label": "A",
      "is_correct": true,
      "explanation": "yield turns a normal function into a generator."
    }
  ],
  "next_lesson_recommendation": "Great job (100.0%)! Promoted to INTERMEDIATE level. Next personalized lesson unlocked with intermediate depth."
}
```

### 3. GET `/adaptive/profile` — Student Profile
```json
{
  "id": "87a50864-884e-484b-a12f-c6d9ddac732b",
  "user_id": "a330ec6f-b83d-4722-995d-739b653cff3a",
  "current_level": "intermediate",
  "total_sessions": 8,
  "quizzes_completed": 6,
  "average_score": 85.5
}
```

---

Interactive docs: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)

