# ConstructERP 🏗️

**Construction Project Management Suite** — a FastAPI backend with multi-tenancy, RBAC, file management, and AI agent capabilities.

![Version](https://img.shields.io/badge/version-0.4.0-amber)
![Status](https://img.shields.io/badge/status-active-green)

## Features

- **Multi-tenancy** — Tenant isolation on all data (projects, tasks, budget, POs, files). Admins see all tenants; users see only their own.
- **RBAC** — 4 roles (admin, project_manager, accounting, viewer) with section-level access control enforced server-side.
- **Projects** — Create, view, and manage construction projects with budget tracking.
- **Tasks** — Gantt-chart-style task scheduling with timeline visualization.
- **Resources** — Track labor, equipment, and materials inventory.
- **Budget** — Cost breakdown with budget vs committed vs spent tracking.
- **Procurement** — Purchase order management with auto-numbered POs (PO-YYYY-NNN).
- **Subcontractors** — Subcontractor directory with contract and progress tracking.
- **Change Orders** — Track scope changes with cost and schedule impact.
- **File Upload** — Authenticated file uploads with auto-classification, local/S3 storage, download, and delete.
- **AI Agent** — Natural language commands, morning briefings, budget analysis, and conversational chat (OpenAI/Ollama backends).
- **Tenant Management** — Admin-only tenant CRUD with user assignment.

## Tech Stack

| Layer | Technology |
|---|---|
| **API** | FastAPI + Pydantic v2 |
| **ORM** | SQLAlchemy 2.0 (Mapped style) |
| **Database** | SQLite (dev) / PostgreSQL (prod) |
| **Auth** | JWT + bcrypt, RBAC dependencies |
| **Storage** | Local filesystem / S3 / MinIO |
| **AI** | OpenAI / Ollama (optional) |
| **Tests** | pytest + httpx TestClient |
| **Deployment** | Docker / docker-compose |

## Quick Start

### Local dev (zero setup)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8787
# Open http://localhost:8787/docs
```

### Docker

```bash
cp backend/.env.example .env  # edit secrets
docker compose up -d
# API at http://localhost:8000/docs
# MinIO console at http://localhost:9001
```

### Run tests

```bash
cd backend
python -m pytest tests/test_api.py -v
```

## Demo Accounts

Seeded automatically on first run (when `SEED_DEMO_USERS=true`):

| Email | Password | Role |
|---|---|---|
| admin@constructerp.dev | admin123 | admin |
| pm@constructerp.dev | pm123 | project_manager |
| accounting@constructerp.dev | acct123 | accounting |
| viewer@constructerp.dev | viewer123 | viewer |
| superadmin@constructerp.dev | super123 | admin (alias) |
| vendor@constructerp.dev | vendor123 | project_manager (alias) |
| supplier@constructerp.dev | supplier123 | accounting (alias) |

## API Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/auth/token` | public | Login (OAuth2 password flow) |
| POST | `/api/auth/register` | public | Self-signup (viewer role) |
| GET | `/api/auth/me` | user | Current user info |
| GET/POST | `/api/auth/users` | admin | User management |
| PATCH | `/api/auth/users/{id}` | admin | Update user |
| GET/POST | `/api/tenants` | admin | Tenant CRUD |
| GET/POST | `/api/projects` | user/admin | Project CRUD |
| GET/POST | `/api/tasks` | user/admin | Task CRUD |
| GET/POST | `/api/resources` | user/admin | Resource CRUD |
| GET/POST | `/api/budget` | accounting | Budget CRUD |
| GET/POST | `/api/purchase-orders` | accounting | PO CRUD |
| GET/POST | `/api/subcontractors` | PM | Subcontractor CRUD |
| GET/POST | `/api/change-orders` | PM/accounting | Change order CRUD |
| POST | `/api/files/upload` | user | Upload file |
| GET | `/api/files` | user | List files |
| GET | `/api/files/{id}` | user | File metadata |
| GET | `/api/files/{id}/download` | user | Download file |
| DELETE | `/api/files/{id}` | user | Delete file |
| GET | `/api/ai/status` | user | AI agent availability |
| POST | `/api/ai/command` | user | NL command |
| POST | `/api/ai/analyze` | user | Budget analysis |
| GET | `/api/ai/briefing` | user | Morning briefing |
| POST | `/api/ai/chat` | user | Conversational chat |
| GET | `/api/health` | public | Health check |
| GET | `/api/state` | user | Full app state (single request) |

## Test Suite (23 tests)

| Category | Tests | Coverage |
|---|---|---|
| Health & Auth | 4 | Public health, login, bad credentials, auth required |
| RBAC | 3 | Viewer can't write, PM restricted, accounting restricted |
| Seed Data | 1 | Seeded reads correct |
| Validation | 1 | Empty name / invalid progress rejected |
| PO Auto-number | 1 | Year-aware PO numbering |
| Self-signup + Admin | 1 | Public register, admin promote |
| Role Aliases | 1 | Vendor→PM, Supplier→accounting mapping |
| Multi-tenancy | 3 | Tenant CRUD, read isolation, record isolation |
| File Upload | 4 | Auth required, upload+list+download+delete, tenant isolation, validation |
| AI Agent | 4 | Auth required, status, graceful degradation, health reports |

## Configuration

See `backend/.env.example` for all options. Key settings:

- `DATABASE_URL` — SQLite (dev) or PostgreSQL (prod)
- `SECRET_KEY` — JWT signing key (auto-generated in dev, set explicitly in prod)
- `STORAGE_BACKEND` — `local` or `s3`
- `AI_PROVIDER` — `openai`, `ollama`, or `disabled`
- `SEED_DEMO_USERS` — seed demo accounts on startup

## License

MIT