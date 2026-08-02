# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

求职邮迹 (Job Mail Agent) — an intelligent job-application email management system. Connects to user email accounts via IMAP, uses LLM (DeepSeek) to classify and extract structured information from job-related emails, matches emails to tracked job applications, generates reply drafts, and executes actions after human review.

## Commands

### Backend (Python)

```bash
# Install dependencies (from backend/)
pip install -e ".[dev]"

# Run development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Run all tests
pytest

# Run a single test file
pytest tests/unit/agents/test_classification_schemas.py

# Run tests matching a keyword
pytest -k "classification"

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Lint
ruff check app/ tests/

# Auto-fix lint issues
ruff check --fix app/ tests/

# Generate a new Alembic migration (from backend/)
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

### Frontend (Node.js)

```bash
# Install dependencies (from frontend/)
npm install

# Development server (proxies /api to localhost:8000)
npm run dev

# Type-check
npm run type-check

# Unit tests (Vitest)
npm test

# E2E tests (Playwright)
npm run test:e2e
```

## Architecture

### Backend Layers (`backend/app/`)

The backend follows a clean-architecture layering:

| Layer | Path | Responsibility |
|-------|------|---------------|
| **API** | `api/v1/endpoints/` | FastAPI route handlers; thin, delegates to application services |
| **Application** | `application/` | Use-case orchestration; services like `SingleEmailAnalysisService`, `JobMailWorkflowService`, `EmailAccessService`, `ReviewTaskService` |
| **Domain** | `domain/` | Enums and domain value objects (e.g., `ApplicationStage`, `WorkflowRunStatus`) — no business logic |
| **Infrastructure** | `infrastructure/` | DB models (SQLAlchemy), repositories, LLM chat model factory, checkpoint persistence, email formatting, credential resolver |
| **Agents** | `agents/` | LLM agents with structured output: classification, extraction, application matching, reply generation |
| **Workflows** | `workflows/` | LangGraph state machine (`graph.py`) and Pydantic state model (`state.py`) |

Dependency direction: `api` → `application` → `domain` + `infrastructure` + `agents`. Application services may also call infrastructure and agents directly.

### LangGraph Workflow (`workflows/graph.py`)

The core email processing pipeline is a LangGraph state graph with these nodes:

```
START → load_email → classify_email → extract_information → validate_results
    → persist_analysis → match_application → human_review (interrupt)
    → execute_review → [generate_reply → human_review] → finalize → END
```

- **Interrupt/resume**: `human_review` calls `langgraph.types.interrupt()` to pause. The HTTP review endpoint resumes via `Command(resume=...)`.
- **Retry**: Classification, extraction, application, and reply nodes each get one automatic retry on failure.
- **Checkpointing**: SQLite with AES encryption (`infrastructure/checkpoint/sqlite.py`). Each workflow run has a unique `thread_id` for LangGraph checkpointing.
- **State**: `WorkflowState` (Pydantic) carries the full pipeline state including `prepared_email`, `classification`, `extraction`, `application_candidates`, `reply_draft_id`, `retry_counts`, etc.

### Agent Design Pattern (`agents/`)

Each agent follows the same pattern:
1. A Pydantic `schemas.py` defines `*Input` and `*Output` models with strict validation.
2. `agent.py` has a `from_model(cls, model: BaseChatModel)` factory that uses `model.with_structured_output()`.
3. Prompts are loaded from versioned `.txt` files in `prompts/<agent_name>/v<N>.txt` via `load_prompt()`.
4. Agents are injected into application services, never called directly from API handlers.

### Database

- **Business data**: MySQL 8 via SQLAlchemy + PyMySQL (`infrastructure/db/models/`). Key entities: `Email`, `EmailAnalysis`, `JobApplication`, `ReviewTask`, `ReplyDraft`, `Task`, `InterviewRound`, `EmailAccount`, `Reminder`, `WorkflowRun`, `AutomationRule`, `ApplicationEvent`, `ActionExecution`.
- **Checkpoint/state**: SQLite at `runtime/checkpoints.sqlite` (encrypted, excluded from git).
- **Migrations**: Alembic in `migrations/`. Uses `compare_type=True`. The env.py imports all models to detect schema changes.
- **Repository pattern**: Repositories in `infrastructure/db/repositories/` encapsulate data access.

### Configuration (`core/config.py`)

Pydantic Settings with `JOB_MAIL_` prefix. Reads from `.env` files (project root and `backend/`). Key settings: `database_url`, `llm_provider`/`llm_model`/`llm_api_key`, `checkpoint_path`, `checkpoint_encryption_key`, `automation_enabled`, `automation_poll_seconds`. Email credentials are stored as environment variable references in the DB (`credential_ref`), never persisted directly.

### LLM Integration (`infrastructure/llm/`)

MVP supports DeepSeek only (`langchain-deepseek`). The `create_chat_model()` factory produces a `BaseChatModel` — agents depend on the abstraction, not the concrete provider. Provider is configured via `JOB_MAIL_LLM_PROVIDER`.

### Frontend (`frontend/`)

Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router.

- **Views**: Mail (email list/detail), Applications (job tracking), Calendar, Reviews (human-in-the-loop decisions), Mailbox Settings
- **API layer**: `src/api/http.ts` creates an Axios instance with `/api/v1` base URL; `src/api/index.ts` exports typed API functions grouped by resource
- **Types**: `src/types/api.ts` mirrors backend domain enums and response schemas
- **Dev proxy**: Vite proxies `/api` to `http://127.0.0.1:8000`

### Reference Code (`references/`)

`references/Email-AI-Agent/` is a cloned third-party reference project used during Phase 1 to validate the IMAP→LLM→SMTP concept. It is gitignored; its ideas were reimplemented in the formal architecture. The `experiments/email-ai-agent/` directory contains adaptation experiments from the reference. Do not add new features to these directories.

## Key Design Decisions

- **Human-in-the-Loop**: All high-risk actions (reply sending, application creation, stage transitions) go through `ReviewTask` records. The workflow pauses at `human_review` via LangGraph interrupt; the user approves/rejects through the Reviews UI, which resumes the graph.
- **Idempotency**: Reply sending uses `idempotency_key` derived from `workflow:{review_task_id}` to prevent duplicate sends.
- **Email credentials**: Stored as env var references (e.g., `JOB_MAIL_EMAIL_CREDENTIAL_TEST_163`) in the DB `credential_ref` column. The `EnvironmentCredentialResolver` reads the actual value from environment variables at runtime — authorization codes are never persisted to the database.
- **Agent traces**: Each workflow run records structured traces (agent name, node, prompt version, confidence, duration, status) in the `agent_trace` JSON column of `workflow_runs`.
- **Analysis versioning**: `EmailAnalysis` supports multiple versions per email; only one is `is_current`.
- **Single active workflow**: Starting a new workflow for an email returns the existing active run if one exists (PENDING/RUNNING/WAITING_REVIEW).

## Tests

- **Backend**: pytest in `backend/tests/`. Unit tests under `tests/unit/`, integration tests under `tests/integration/`. Test fixtures in `tests/fixtures/emails/`.
- **Frontend**: Vitest for unit tests, Playwright for E2E. Test files co-located or in `__tests__` directories.
- No test database is configured — tests that hit the database need a running MySQL instance.
