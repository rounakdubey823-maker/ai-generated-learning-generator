# AI Learning Generator — Full-Stack Setup Guide

## Overview

| Layer | Stack | Port |
|-------|-------|------|
| Backend | FastAPI + SQLite (aiosqlite) | 8000 |
| Frontend | React + Vite + TypeScript | 5173 |

---

## Prerequisites

- **Python 3.11+** with a virtual environment in `backend/.venv`
- **Node.js 18+** and npm

---

## 1 — Backend

### Install & Start

```bash
# From the repo root
cd backend

# Activate the existing venv
source .venv/bin/activate       # macOS/Linux

# Install Python dependencies (if not already done)
pip install -r requirements.txt

# Copy env and configure (DB + AI keys)
cp ../.env.example ../.env
# Edit ../.env — set OPENAI_API_KEY or GOOGLE_API_KEY
# Leave MOCK_AI_IN_DEV=true to use mock responses without a key

# Start the development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **Root**: http://localhost:8000/
- **Swagger UI**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc
- **Health**: http://localhost:8000/api/v1/health

### Run Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
# Expected: 54 passed
```

---

## 2 — Frontend

### Install & Start

```bash
cd frontend

# Install dependencies (first time only)
npm install

# .env is already configured for local dev:
# VITE_API_BASE_URL=http://localhost:8000/api/v1

# Start the Vite dev server
npm run dev
```

The app will open at **http://localhost:5173**.

### Type-check

```bash
cd frontend
npx tsc --noEmit
```

### Production Build

```bash
cd frontend
npm run build       # outputs to frontend/dist/
npm run preview     # serves the built bundle locally
```

---

## 3 — Environment Variables

### Backend (`.env` at repo root or `backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `openai` | `openai` or `google` |
| `OPENAI_API_KEY` | *(empty)* | Required for real OpenAI output |
| `GOOGLE_API_KEY` | *(empty)* | Required for real Gemini output |
| `MOCK_AI_IN_DEV` | `true` | Use mock responses when no key is set |
| `DATABASE_URL` | SQLite (`dev.db`) | Change for PostgreSQL in production |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:5173` | CORS allowed origins |

### Frontend (`frontend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Backend API base URL |

---

## 4 — API Endpoints used by the Frontend

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Health check shown in header indicator |
| `POST` | `/api/v1/generate` | Generate notes/summary/quiz from a topic |
| `POST` | `/api/v1/documents/upload` | Upload PDF, extract text, optionally generate |

---

## 5 — Features

- **Topic input** with level (beginner / intermediate / advanced) and language selection (10 languages)
- **Content type selection**: Notes, Summary, Quiz
- **PDF upload** with drag-and-drop, text extraction preview, and optional AI generation
- **Interactive quiz**: reveal answer button per question
- **Save to library**: results persisted in `localStorage` (up to 50 items), displayed as a card grid
- **Loading state**: animated spinner while awaiting the API
- **Error state**: inline alert showing the backend error message
- **API health indicator**: live coloured dot in the header showing backend connectivity
- **Mock badge**: clearly labelled when content comes from the mock provider
- **Responsive**: single-column on mobile, two-column sidebar layout on desktop

---

## 6 — Project Structure

```
ai generator/
├── backend/
│   ├── main.py                       # FastAPI app entry point
│   ├── requirements.txt
│   ├── app/
│   │   ├── api/v1/endpoints/         # generate, documents, auth, health, learning
│   │   ├── core/                     # config, errors, security
│   │   ├── db/                       # session, init_db
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   ├── schemas/                  # Pydantic request/response schemas
│   │   └── services/                 # pdf_extractor, ai_service
│   └── tests/                        # 54 pytest tests
├── ai_module/
│   ├── generator.py                  # Orchestrates AI provider calls
│   ├── providers/                    # openai, google, mock providers
│   └── schemas.py                    # Shared Pydantic types
├── frontend/
│   ├── src/
│   │   ├── api/client.ts             # Typed fetch-based API client
│   │   ├── App.tsx                   # Main dashboard (form + results + saved library)
│   │   ├── App.css                   # Component-level styles
│   │   └── index.css                 # Global design tokens and reset
│   ├── .env                          # VITE_API_BASE_URL for local dev
│   ├── .env.example
│   └── index.html
└── .env.example                      # Backend environment template
```
