# ConstructERP — Mesh Collaboration

## Project
Construction ERP backend with multi-tenancy, RBAC, file management, AI agent.
FastAPI + SQLAlchemy + SQLite/PostgreSQL. Docker-ready.

## Current State (v0.3.0)
- ✅ FastAPI backend with Pydantic v2 schemas + validation
- ✅ JWT auth with bcrypt, 4-role RBAC (admin, PM, accounting, viewer)
- ✅ Generic CRUD router factory (make_crud_router) — DRY for all 7 entities
- ✅ Multi-tenancy with tenant_id auto-filtering on all reads/writes
- ✅ Tenant management endpoints (admin-only CRUD)
- ✅ File upload with local/S3 storage, auto-classification, auth + tenant isolation
- ✅ AI agent module (OpenAI/Ollama) — chat, command, briefing, budget analysis
- ✅ Docker + docker-compose (API + PostgreSQL + MinIO)
- ✅ 23/23 tests passing (auth, RBAC, validation, tenancy, files, AI)

## Architecture
- **Backend:** `backend/app/` — FastAPI with modular structure
  - `main.py` — app entrypoint, lifespan, router registration
  - `models.py` — SQLAlchemy ORM (10 models: Tenant, Project, Task, Resource, BudgetItem, PurchaseOrder, Subcontractor, ChangeOrder, FileUpload, User)
  - `schemas.py` — Pydantic v2 request/response schemas with Literal enums
  - `crud.py` — Generic CRUD router factory with tenant-aware filtering
  - `auth.py` — Auth endpoints (login, register, user management)
  - `security.py` — JWT, password hashing, RBAC dependencies
  - `tenants.py` — Tenant management endpoints
  - `files.py` — File upload/download/delete with storage abstraction
  - `storage.py` / `storage_local.py` / `storage_s3.py` — Storage backends
  - `ai.py` — AI agent (OCR, NL commands, briefings, chat)
  - `ai_routes.py` — AI API routes (auth-protected, tenant-scoped)
  - `seed.py` — Demo data seeding
  - `config.py` — Pydantic settings from env/.env

## Open Tasks / Next Steps

### High Priority
- [ ] **Add Alembic migrations** — replace create_all() with alembic upgrade head
- [ ] **Add structured logging** — request/response logging middleware
- [ ] **Add global exception handler** — 500 with error type, no stack trace leak
- [ ] **Add pagination headers** — X-Total-Count, X-Page, X-Per-Page on list endpoints

### Medium Priority
- [ ] **Add OCR pipeline** — tesseract integration for file text extraction
- [ ] **Add frontend** — React/Vite SPA replacing the HTML prototype
- [ ] **Add WebSocket** — real-time notifications for tender deadlines
- [ ] **Add rate limiting** — slowapi or custom middleware

### Low Priority
- [ ] **Add Alembic autogenerate** — detect model changes and create migrations
- [ ] **Add CI/CD** — GitHub Actions for test + lint + build
- [ ] **Add API versioning** — /api/v1/ prefix
- [ ] **Add OpenAPI customization** — examples, descriptions, error schemas

## How to Collaborate
1. Pick a task from the list above
2. Edit the relevant file in `backend/app/`
3. Run tests: `cd backend && python -m pytest tests/test_api.py -v`
4. Update this file's task list when done

## Agents
- **Hermes Agent** — primary developer, full tool access