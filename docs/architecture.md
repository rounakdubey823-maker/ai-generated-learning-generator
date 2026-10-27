# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Browser                         │
│               React + Vite (frontend/)                      │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP/REST
┌────────────────────────────▼────────────────────────────────┐
│              FastAPI Backend (backend/)                      │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │  /auth   │  │/learning │  │ /health  │  │  future   │  │
│  └────┬─────┘  └────┬─────┘  └──────────┘  └───────────┘  │
│       │             │                                       │
│  ┌────▼─────────────▼────────────────────────────────────┐ │
│  │             Services Layer                             │ │
│  │   UserService   │   ai_service.generate_content()     │ │
│  └────┬─────────────────────────┬─────────────────────────┘ │
│       │                         │                           │
│  ┌────▼────────┐    ┌───────────▼───────────┐              │
│  │  SQLAlchemy │    │  AI Module (ai_module/) │             │
│  │  (async DB) │    │  prompts.py / utils.py  │             │
│  └────┬────────┘    └───────────┬────────────┘             │
│       │                         │                           │
│  ┌────▼────────┐    ┌───────────▼────────────┐             │
│  │ PostgreSQL  │    │  OpenAI API / Google    │             │
│  │ (SQLite dev)│    │  Gemini API             │             │
│  └─────────────┘    └────────────────────────┘             │
└─────────────────────────────────────────────────────────────┘
```

## Module Responsibilities

| Directory | Responsibility |
|-----------|----------------|
| `backend/app/core/` | Config, security (JWT), shared utilities |
| `backend/app/db/` | SQLAlchemy engine, session, Base |
| `backend/app/models/` | ORM table definitions |
| `backend/app/schemas/` | Pydantic request/response models |
| `backend/app/api/v1/endpoints/` | FastAPI route handlers |
| `backend/app/services/` | Business logic, AI provider wrappers |
| `ai_module/` | Reusable prompt templates and AI utilities |
| `frontend/` | React UI (to be scaffolded) |

## Data Flow — Content Generation

```
User submits topic
      │
      ▼
POST /api/v1/learning/generate
      │
      ▼
GenerateRequest (Pydantic validation)
      │
      ▼
ai_service.generate_learning_content()
      │
      ├── if OPENAI_API_KEY → OpenAI Chat Completions API
      ├── if GOOGLE_API_KEY → Google Gemini API
      └── else              → Stub response (dev mode)
      │
      ▼
LearningContent saved to DB
      │
      ▼
LearningContentOut returned to client
```
