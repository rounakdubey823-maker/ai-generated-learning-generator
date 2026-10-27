# Backend Handover Documentation

**Project**: AI-Generated Learning Generator  
**Document Version**: 1.0.0  
**Target Audience**: Frontend Engineering Team, DevOps, Integration Engineers  
**Source of Truth**: `INTEGRATION_CONTRACT.md` & Live Backend Implementation  
**Test Status**: **122 passed, 0 failed** (100% passing test suite)

---

## 1. Backend Architecture & Folder Structure

The backend is built with **FastAPI** (Python 3.11+ / 3.13 compatible), utilizing **SQLAlchemy 2.0 (async)** with SQLite (`aiosqlite`) for local development, and integrates directly with the root-level `ai_module/` package.

```
ai generator/
├── ai_module/                       # Standalone, framework-agnostic AI & progression layer
│   ├── __init__.py                  # Exports: generate, generate_adaptive_content, calculate_next_level
│   ├── generator.py                 # Core AI generator, adaptive generator, and progression rules
│   ├── prompts.py                   # System & user prompt templates for notes, summary, quiz
│   ├── schemas.py                   # Pydantic schemas: LearningLevel, ContentType, AIRequest, etc.
│   ├── utils.py                     # Topic sanitization and token/character counting helpers
│   └── providers/                   # AI provider clients
│       ├── base.py                  # BaseProvider abstract class & ProviderError
│       ├── openai_provider.py       # OpenAI GPT-4o-mini integration
│       ├── google_provider.py       # Google Gemini 1.5 Flash integration
│       └── mock_provider.py         # Deterministic mock provider for local testing
│
├── backend/                         # FastAPI Application Root
│   ├── main.py                      # Application entry point, lifespan, CORS, error handlers
│   ├── conftest.py                  # Pytest fixtures and sys.path configuration
│   ├── pytest.ini                   # Asyncio test configuration
│   ├── requirements.txt             # Locked backend dependencies
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── router.py            # API v1 aggregator router
│   │   │   └── endpoints/
│   │   │       ├── health.py        # GET /api/v1/health (liveness & DB probe)
│   │   │       ├── auth.py          # POST /api/v1/auth/register, POST /api/v1/auth/login
│   │   │       ├── generate.py      # POST /api/v1/generate (direct topic generation)
│   │   │       ├── documents.py     # POST /api/v1/documents/upload (PDF extraction)
│   │   │       ├── adaptive.py      # /api/v1/adaptive/* (profile, session, submit, progress)
│   │   │       └── learning.py      # /api/v1/learning/* (legacy persistence routes)
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic Settings (.env configuration)
│   │   │   ├── security.py          # JWT creation and decoding
│   │   │   └── errors.py            # Unified error envelope & custom exceptions
│   │   ├── db/
│   │   │   └── session.py           # Async SQLAlchemy engine, session maker, get_db, init_db
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   │   ├── __init__.py          # Model registration for SQLAlchemy Base
│   │   │   ├── user.py              # User
│   │   │   ├── adaptive.py          # StudentProfile, LearningSession, QuizAttempt
│   │   │   └── learning_content.py  # LearningContent (legacy)
│   │   ├── schemas/                 # Pydantic request/response validation schemas
│   │   │   ├── user.py              # UserCreate, UserOut, Token
│   │   │   ├── generate.py          # GenerateRequest, GenerateResponse
│   │   │   ├── document.py          # DocumentUploadResponse
│   │   │   └── adaptive.py          # StartSessionRequest, LearningSessionOut, QuizSubmission, etc.
│   │   └── services/
│   │       ├── ai_service.py        # Service wrapper around ai_module
│   │       └── pdf_extractor.py     # Secure pypdf text extraction with page & size limits
│   └── tests/                       # Automated pytest suite (122 tests)
│       ├── test_adaptive.py         # 62 tests (progression, boundaries, server grading, persistence)
│       ├── test_auth.py             # 6 tests (registration, login, invalid credentials)
│       ├── test_documents.py        # 17 tests (PDF validation, extraction, size limits)
│       ├── test_generate.py         # 24 tests (content generation, schemas, mock providers)
│       ├── test_health.py           # 9 tests (health payload, uptime, DB connectivity)
│       └── test_smoke.py            # 4 tests (root metadata, 404/422 envelopes)
```

---

## 2. API Endpoints Reference

All endpoints are hosted under prefix `/api/v1`. The OpenAPI interactive docs are live at `http://localhost:8000/api/v1/docs`.

### Standard Error Envelope
All error responses adhere to a consistent JSON envelope:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable description of the error",
    "detail": null
  }
}
```

Common HTTP error codes:
- `400 Bad Request`: `BAD_REQUEST` (e.g. duplicate quiz submission, already registered email).
- `401 Unauthorized`: `UNAUTHORIZED` (invalid credentials or expired JWT).
- `404 Not Found`: `NOT_FOUND` (unknown session or resource).
- `413 Payload Too Large`: `PAYLOAD_TOO_LARGE` (file exceeds upload size limits).
- `422 Unprocessable Entity`: `VALIDATION_ERROR`, `DOCUMENT_INVALID_TYPE`, `DOCUMENT_NO_TEXT`, `DOCUMENT_EMPTY`, `DOCUMENT_ENCRYPTED`.
- `503 Service Unavailable`: `SERVICE_UNAVAILABLE` (missing API keys when mock mode is disabled).

---

### Endpoints Table

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/` | No | Root metadata & redirect documentation URLs |
| `GET` | `/api/v1/health` | No | Detailed health status, uptime, and database connectivity |
| `POST` | `/api/v1/auth/register` | No | Register a new user |
| `POST` | `/api/v1/auth/login` | No | Login via OAuth2 form to receive a JWT Bearer token |
| `POST` | `/api/v1/generate` | No | Generate educational notes, summary, or quiz on a topic |
| `POST` | `/api/v1/documents/upload` | No | Upload PDF, extract clean text, optionally generate content |
| `GET` | `/api/v1/adaptive/profile` | Optional* | Retrieve student proficiency level and cumulative stats |
| `POST` | `/api/v1/adaptive/session` | Optional* | Start adaptive session (strips quiz answers for client safety) |
| `GET` | `/api/v1/adaptive/session/{id}` | Optional* | Fetch session details and client-safe quiz |
| `POST` | `/api/v1/adaptive/session/{id}/quiz/submit` | Optional* | Server-side quiz evaluation, grading, and level update |
| `GET` | `/api/v1/adaptive/progress` | Optional* | Retrieve student historical quiz attempts and progression |
| `POST` | `/api/v1/learning/generate` | No | (Legacy) Generate and persist content object |
| `GET` | `/api/v1/learning/{content_id}` | No | (Legacy) Retrieve stored content object |

*\*Note on Optional Auth*: The `/adaptive/*` endpoints automatically support **both** authenticated users (via `Authorization: Bearer <token>`) and guest/demo users (fallback to an internal demo student account). The frontend can immediately test adaptive learning without requiring an active login session!

---

### Detailed Endpoint Specifications

#### 1. GET `/api/v1/health`
- **Response (200 OK)**:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "development",
  "uptime_seconds": 124.5,
  "dependencies": {
    "database": {
      "status": "ok"
    }
  }
}
```

#### 2. POST `/api/v1/auth/register`
- **Request**:
```json
{
  "email": "student@example.com",
  "password": "SecurePassword123!",
  "full_name": "Jane Student"
}
```
- **Response (201 Created)**:
```json
{
  "id": "a330ec6f-b83d-4722-995d-739b653cff3a",
  "email": "student@example.com",
  "full_name": "Jane Student",
  "is_active": true,
  "created_at": "2026-10-28T00:00:00Z"
}
```

#### 3. POST `/api/v1/auth/login`
- **Request**: Form Data (`application/x-www-form-urlencoded`):
  - `username`: `student@example.com`
  - `password`: `SecurePassword123!`
- **Response (200 OK)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### 4. POST `/api/v1/generate`
- **Request**:
```json
{
  "topic": "Python Generators",
  "learning_level": "beginner",
  "language": "English",
  "content_type": "notes"
}
```
*Valid `learning_level` values*: `"beginner"`, `"intermediate"`, `"advanced"`.  
*Valid `content_type` values*: `"notes"`, `"summary"`, `"quiz"`.
- **Response (200 OK)**:
```json
{
  "id": "9d903f0d-efc2-40ee-b630-fbf8f0814fa8",
  "topic": "Python Generators",
  "learning_level": "beginner",
  "language": "English",
  "content_type": "notes",
  "content": {
    "title": "Introduction to Python Generators",
    "sections": [
      {
        "heading": "What is a Generator?",
        "body": "Generators allow you to declare a function that behaves like an iterator using yield."
      }
    ]
  },
  "provider": "openai",
  "model": "gpt-4o-mini",
  "is_mock": false,
  "generated_at": "2026-10-28T00:00:00Z"
}
```

#### 5. POST `/api/v1/documents/upload`
- **Request**: `multipart/form-data`:
  - `file`: PDF binary file (must begin with `%PDF-` signature)
  - `generate`: (boolean, optional, default `false`)
  - `topic`: (string, optional)
  - `learning_level`: (string, optional, `"beginner"` | `"intermediate"` | `"advanced"`)
  - `content_type`: (string, optional, `"notes"` | `"summary"` | `"quiz"`)
- **Response (200 OK)**:
```json
{
  "filename": "lecture_01.pdf",
  "page_count": 5,
  "extracted_characters": 3420,
  "preview": "Chapter 1: Principles of Operating Systems...",
  "generated": null
}
```

#### 6. GET `/api/v1/adaptive/profile`
- **Response (200 OK)**:
```json
{
  "id": "e4c5b33e-b816-43e6-a212-3bfa59a41e97",
  "user_id": "a330ec6f-b83d-4722-995d-739b653cff3a",
  "current_level": "Beginner",
  "total_sessions": 4,
  "quizzes_completed": 3,
  "average_score": 86.67
}
```

#### 7. POST `/api/v1/adaptive/session`
- **Request**:
```json
{
  "topic": "Binary Search Trees",
  "difficulty": "Beginner",
  "language": "English"
}
```
*Note*: `difficulty` is optional. If omitted, it automatically adopts the student's `profile.current_level`.
- **Response (201 Created)**:
```json
{
  "session_id": "78da5a33-bc81-424d-8cf7-21fb6552b72f",
  "topic": "Binary Search Trees",
  "difficulty": "Beginner",
  "language": "English",
  "lesson": {
    "title": "Binary Search Trees Fundamentals",
    "sections": [
      {
        "heading": "Introduction",
        "body": "A Binary Search Tree is a node-based binary tree data structure..."
      }
    ]
  },
  "quiz": [
    {
      "index": 0,
      "question": "What is the average time complexity of searching a balanced BST?",
      "options": [
        {"label": "A", "text": "O(log n)"},
        {"label": "B", "text": "O(n)"},
        {"label": "C", "text": "O(1)"},
        {"label": "D", "text": "O(n log n)"}
      ]
    }
  ],
  "is_completed": false
}
```
*(Notice: The correct answers and explanations are stripped from this response to prevent frontend cheating).*

#### 8. POST `/api/v1/adaptive/session/{session_id}/quiz/submit`
- **Request**:
```json
{
  "answers": [
    {"question_index": 0, "selected_label": "A"},
    {"question_index": 1, "selected_label": "B"},
    {"question_index": 2, "selected_label": "A"},
    {"question_index": 3, "selected_label": "C"},
    {"question_index": 4, "selected_label": "D"}
  ]
}
```
- **Response (200 OK)**:
```json
{
  "session_id": "78da5a33-bc81-424d-8cf7-21fb6552b72f",
  "total_questions": 5,
  "correct_count": 4,
  "score_percentage": 80.0,
  "previous_level": "Beginner",
  "new_level": "Intermediate",
  "level_changed": true,
  "details": [
    {
      "question_index": 0,
      "question": "What is the average time complexity of searching a balanced BST?",
      "selected_label": "A",
      "correct_label": "A",
      "is_correct": true,
      "explanation": "Because balanced BSTs halve the search space at each level, lookup is O(log n)."
    }
  ],
  "next_lesson_recommendation": "Great job (80.0%)! Promoted to INTERMEDIATE level. Next personalized lesson unlocked with intermediate depth."
}
```

#### 9. GET `/api/v1/adaptive/progress`
- **Response (200 OK)**:
```json
[
  {
    "attempt_id": "7bc26e82-e3a8-4bb4-9ce5-aef95b36aa88",
    "session_id": "78da5a33-bc81-424d-8cf7-21fb6552b72f",
    "topic": "Binary Search Trees",
    "score_percentage": 80.0,
    "previous_level": "Beginner",
    "new_level": "Intermediate",
    "created_at": "2026-10-28T00:15:30Z"
  }
]
```

---

## 3. Database Models & Persisted Data

The SQLite database (`dev.db`) is managed via async SQLAlchemy ORM models.

### 1. `users` Table (`app.models.user.User`)
- `id` (String(36), PK): UUID primary key.
- `email` (String(255), Unique, Indexed): User email.
- `hashed_password` (String(255)): Bcrypt salted hash.
- `full_name` (String(255), Nullable): Full display name.
- `is_active` (Boolean, default `True`).
- `created_at`, `updated_at` (DateTime with timezone).

### 2. `student_profiles` Table (`app.models.adaptive.StudentProfile`)
- `id` (String(36), PK): UUID primary key.
- `user_id` (String(36), FK $\rightarrow$ `users.id`, Unique, Indexed): Associated student user.
- `current_level` (String(50), default `"Beginner"`): Current proficiency level (`"Beginner"`, `"Intermediate"`, `"Advanced"`).
- `total_sessions` (Integer, default `0`): Cumulative count of generated learning sessions.
- `quizzes_completed` (Integer, default `0`): Cumulative count of submitted quizzes.
- `average_score` (Float, default `0.0`): Running weighted mean score percentage.
- `created_at`, `updated_at` (DateTime with timezone).

### 3. `learning_sessions` Table (`app.models.adaptive.LearningSession`)
- `id` (String(36), PK): UUID session identifier.
- `user_id` (String(36), FK $\rightarrow$ `users.id`, Indexed).
- `topic` (String(512)): The topic of study.
- `difficulty` (String(50)): TitleCase level when generated (`"Beginner"`, `"Intermediate"`, `"Advanced"`).
- `lesson_content` (JSON): Structured lesson notes (`title`, `sections`).
- `quiz_data` (JSON): **Full quiz containing secret answer keys** (`questions`, `correct_label`, `explanation`). Never sent directly to the client before grading.
- `is_completed` (Boolean, default `False`): True once the quiz has been submitted and graded. Prevents replay attacks.
- `created_at` (DateTime with timezone).

### 4. `quiz_attempts` Table (`app.models.adaptive.QuizAttempt`)
- `id` (String(36), PK): UUID attempt identifier.
- `session_id` (String(36), FK $\rightarrow$ `learning_sessions.id`, Indexed).
- `user_id` (String(36), FK $\rightarrow$ `users.id`, Indexed).
- `submitted_answers` (JSON): Array of answers submitted by the student (`[{"question_index": 0, "selected_label": "A"}]`).
- `total_questions` (Integer): Total questions in the quiz.
- `correct_count` (Integer): Count of correctly evaluated questions.
- `score_percentage` (Float): Calculated percentage $(0.0 - 100.0)$.
- `previous_level` (String(50)): Proficiency level before submission.
- `new_level` (String(50)): Updated proficiency level after grading.
- `feedback` (JSON): Detailed per-question feedback including explanations unlocked after submission.
- `created_at` (DateTime with timezone).

---

## 4. Integration with `ai_module`

The backend interfaces with the `ai_module/` package located at the repository root via two primary functions:

```python
from ai_module import calculate_next_level, generate_adaptive_content
```

### 1. `generate_adaptive_content(topic, difficulty, language, config)`
- Invoked when `POST /api/v1/adaptive/session` is called.
- Generates both tailored lesson content and a 5-question multiple choice quiz suited to the requested difficulty.
- Automatically handles provider fallback and mock labeling if no API keys are configured locally.

### 2. `calculate_next_level(current_level, score_percentage)`
- Invoked during `POST /api/v1/adaptive/session/{id}/quiz/submit`.
- Calculates the progression transition and returns exact TitleCase strings: `"Beginner"`, `"Intermediate"`, or `"Advanced"`.

---

## 5. Server-Side Quiz Grading & Scoring Formula

### Zero Client Trust Architecture
1. The client **never** receives `correct_label` or `explanation` when retrieving a quiz.
2. The client submits only an array of `question_index` and `selected_label` values.
3. The server looks up the persistent `session.quiz_data` stored securely in the database.
4. Each answer is evaluated strictly on the server:
   ```python
   correct = question.get("correct_label", "").strip().upper()
   selected = submitted_map.get(idx, "").strip().upper()
   is_correct = bool(selected and selected == correct)
   ```
5. **Score Formula**:
   $$\text{score\_percentage} = \text{round}\left(\frac{\text{correct\_count}}{\text{total\_questions}} \times 100.0, 2\right)$$
6. The updated level is calculated:
   ```python
   new_level = calculate_next_level(previous_level, score_percentage)
   ```
7. Both the session status (`is_completed = True`), the `QuizAttempt` record, and the `StudentProfile` updates (`quizzes_completed`, `average_score`, `current_level`) are committed atomically to the database.

---

## 6. Adaptive Difficulty Rules & Boundary Behavior

Per `INTEGRATION_CONTRACT.md`, the progression engine implements deterministic transitions:

### Core Rules
- **Promotion**: $\text{Score} \ge 80.0\%$ promotes one tier.
- **Demotion**: $\text{Score} < 50.0\%$ demotes one tier.
- **Retention**: $50.0\% \le \text{Score} < 80.0\%$ retains the current tier.
- **Lower Bound Clamp**: `Beginner` cannot go below `Beginner`.
- **Upper Bound Clamp**: `Advanced` cannot go above `Advanced`.
- **Exact Capitalization**: Returned levels are strictly TitleCase (`"Beginner"`, `"Intermediate"`, `"Advanced"`).

### Complete Boundary Matrix

| Current Level | Score: `49%` ($< 50\%$) | Score: `50%` ($50\% \le s < 80\%$) | Score: `79%` ($50\% \le s < 80\%$) | Score: `80%` ($\ge 80\%$) |
|---|---|---|---|---|
| **`Beginner`** | `Beginner` (clamped) | `Beginner` (retained) | `Beginner` (retained) | `Intermediate` (promoted) |
| **`Intermediate`** | `Beginner` (demoted) | `Intermediate` (retained) | `Intermediate` (retained) | `Advanced` (promoted) |
| **`Advanced`** | `Intermediate` (demoted) | `Advanced` (retained) | `Advanced` (retained) | `Advanced` (clamped) |

### Input Validation
`calculate_next_level` validates both inputs:
- Any level outside `("beginner", "intermediate", "advanced")` or non-string input raises a `ValueError`.
- Any score $< 0.0$ or $> 100.0$, non-numeric values, or boolean inputs raise a `ValueError`.

---

## 7. Environment Variables & Security Configuration

Configure your environment by creating a `.env` file in the workspace root or inside `backend/.env`. A template is provided in `.env.example`.

```env
# Application Settings
PROJECT_NAME="AI Learning Generator"
VERSION="0.1.0"
ENVIRONMENT="development"
DEBUG=true

# Security Settings
SECRET_KEY="replace-with-a-random-32-byte-hex-string"
ACCESS_TOKEN_EXPIRE_MINUTES=60
ALGORITHM="HS256"

# Database Connection (Async SQLite for local, PostgreSQL for production)
DATABASE_URL="sqlite+aiosqlite:///./dev.db"

# AI Provider Settings ("openai" | "google")
AI_PROVIDER="openai"
OPENAI_API_KEY=""
OPENAI_MODEL="gpt-4o-mini"
GOOGLE_API_KEY=""
GOOGLE_MODEL="gemini-1.5-flash"
AI_TIMEOUT_SECONDS=30
AI_MAX_RETRIES=2

# Safe Local Mocking
# When true, the backend generates deterministic, typed content if no API key is supplied
MOCK_AI_IN_DEV=true

# Upload and Security Constraints
MAX_UPLOAD_BYTES=10485760     # 10 MB limit
MAX_PDF_PAGES=50
MAX_EXTRACTED_CHARS=20000

# CORS Allowed Origins (Comma-separated)
ALLOWED_ORIGINS="http://localhost:5173,http://localhost:3000"
```

### Security Guarantees
- **No committed secrets**: `.env` and `*.db` are ignored by `.gitignore`.
- **Safe Development**: With `MOCK_AI_IN_DEV=true`, the team can test the complete system locally without entering private API keys.
- **File Upload Protection**: Uploaded PDFs are parsed in-memory/temp storage using `pypdf`, validated by magic bytes `%PDF-`, and temporary files are strictly cleaned up in a `finally` block.

---

## 8. Startup & Testing Commands (macOS)

### Step 1: Set Up Python Virtual Environment
From the repository root:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2: Start the Backend Server
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
The backend will start and log:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Step 3: Run the Complete Backend Test Suite
```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

---

## 9. Frontend Integration Guide

The frontend developer can immediately communicate with the backend.

### 1. Base URL
Set in `frontend/.env`:
```env
VITE_API_BASE_URL="http://localhost:8000/api/v1"
```

### 2. CORS
The backend already permits cross-origin requests from `http://localhost:5173` (Vite) and `http://localhost:3000`.

### 3. Step-by-Step Flow for the Frontend Teammate

```
┌─────────────────┐       GET /api/v1/adaptive/profile       ┌─────────────────┐
│                 │ ───────────────────────────────────────> │                 │
│                 │ <─────────────────────────────────────── │                 │
│                 │      Returns current_level: "Beginner"   │                 │
│                 │                                          │                 │
│                 │       POST /api/v1/adaptive/session      │                 │
│    Frontend     │ ───────────────────────────────────────> │     Backend     │
│   Dashboard     │ <─────────────────────────────────────── │   FastAPI App   │
│                 │      Returns Lesson & Safe Quiz (no key) │                 │
│                 │                                          │                 │
│                 │    POST /api/v1/adaptive/.../quiz/submit │                 │
│                 │ ───────────────────────────────────────> │                 │
│                 │ <─────────────────────────────────────── │                 │
│                 │      Returns Score, Next Level & Answers │                 │
└─────────────────┘                                          └─────────────────┘
```

1. **Check Student Profile**: Call `GET /api/v1/adaptive/profile` to get the student's `current_level` (`"Beginner"` by default) and stats.
2. **Start a Learning Session**: Call `POST /api/v1/adaptive/session` with `{"topic": "..."}`. Render `lesson.sections` as study notes and render `quiz` as a multiple-choice interactive test.
3. **Submit Quiz Answers**: When the user clicks "Submit Quiz", post the answers to `POST /api/v1/adaptive/session/{session_id}/quiz/submit`.
4. **Display Evaluation**: The response gives `score_percentage`, per-question `details` (with `correct_label`, `is_correct`, `explanation`), and the updated `new_level` (`"Beginner"`, `"Intermediate"`, or `"Advanced"`).
5. **View History**: Call `GET /api/v1/adaptive/progress` to render a learning progression chart.

---

## 10. Actual Test Results & Deployment Considerations

### Actual Test Results (Verified 2026-10-28)
```
============================= test session starts ==============================
collected 122 items

backend/tests/test_adaptive.py::TestCalculateNextLevel::test_boundary_scores_and_levels (21 cases) PASSED
backend/tests/test_adaptive.py::TestCalculateNextLevel::test_exact_contract_capitalization_returned_regardless_of_input_casing (7 cases) PASSED
backend/tests/test_adaptive.py::TestCalculateNextLevel::test_invalid_scores_raise_value_error (13 cases) PASSED
backend/tests/test_adaptive.py::TestCalculateNextLevel::test_invalid_levels_raise_value_error (11 cases) PASSED
backend/tests/test_adaptive.py::TestGenerateAdaptiveContentFunction::test_generates_notes_and_quiz PASSED
backend/tests/test_adaptive.py::TestAdaptiveEndpoints (9 integration tests) PASSED
backend/tests/test_auth.py (6 tests) PASSED
backend/tests/test_documents.py (17 tests) PASSED
backend/tests/test_generate.py (24 tests) PASSED
backend/tests/test_health.py (9 tests) PASSED
backend/tests/test_smoke.py (4 tests) PASSED

====================== 122 passed, 23 warnings in 12.80s =======================
```
- **Total Passing Tests**: **122**
- **Failures**: **0**
- **Regressions**: **0**

### Known Limitations
1. **Scanned PDFs**: `pdf_extractor.py` performs digital text extraction (via `pypdf`). Scanned image-only PDFs containing no embedded text layers are rejected with `DOCUMENT_NO_TEXT`. Adding Tesseract OCR would resolve image-only scans.
2. **Local Storage Database**: The local setup uses SQLite (`sqlite+aiosqlite:///./dev.db`). While fast and zero-config for pair programming, concurrent writes are restricted to single-file locks.

### Production Deployment Considerations
1. **Database**: Swap `DATABASE_URL` in `.env` to a managed PostgreSQL instance:
   ```env
   DATABASE_URL="postgresql+asyncpg://user:password@host:5432/learning_db"
   ```
2. **Production Settings**:
   - Set `ENVIRONMENT="production"`.
   - Set `DEBUG=false`.
   - Set `MOCK_AI_IN_DEV=false` and supply a valid `OPENAI_API_KEY` or `GOOGLE_API_KEY`.
   - Generate a cryptographically secure random `SECRET_KEY` (e.g. `openssl rand -hex 32`).
3. **ASGI Server**: Run behind a production ASGI server with multiple Gunicorn Uvicorn workers:
   ```bash
   gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```
