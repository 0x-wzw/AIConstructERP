# ConstructERP — Backend API

A **FastAPI + SQLAlchemy** REST backend for the ConstructERP suite. Runs on
**SQLite** out of the box (zero setup) and is **PostgreSQL-ready** — swap one
env var, no code changes.

## Quick start

```bash
cd backend
uv venv                       # create .venv
uv pip install -r requirements.txt
uv run uvicorn app.main:app --reload --port 8787
```

Then open:
- **Swagger UI:** http://localhost:8787/docs
- **Health:** http://localhost:8787/api/health
- **Full state (one call):** http://localhost:8787/api/state

The database (`constructerp.db`) is created and seeded with demo data on first
launch.

## API

Every resource supports full REST CRUD under `/api`:

| Resource        | Base path                | List filters            |
|-----------------|--------------------------|-------------------------|
| Projects        | `/api/projects`          | `q` (name, location)    |
| Tasks           | `/api/tasks`             | `q` (name)              |
| Resources       | `/api/resources`         | `q` (name, category)    |
| Budget items    | `/api/budget`            | `q` (category)          |
| Purchase orders | `/api/purchase-orders`   | `q` (po#, supplier, item) |
| Subcontractors  | `/api/subcontractors`    | `q` (name, trade)       |
| Change orders   | `/api/change-orders`     | `q` (title)             |

Each supports: `GET /` (list, `skip`/`limit`/`q`), `POST /`, `GET /{id}`,
`PATCH /{id}`, `DELETE /{id}`. Purchase-order numbers (`PO-YYYY-NNN`) are
auto-generated when omitted.

## Authentication & RBAC

JWT bearer auth (OAuth2 password flow). **All resource endpoints require a
token**; writes additionally require a role. `/api/health` stays public.

Login to get a token, then send `Authorization: Bearer <token>`:

```bash
TOKEN=$(curl -s -X POST http://localhost:8787/api/auth/token \
  -d 'username=admin@constructerp.dev&password=admin123' | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8787/api/projects
```

Auth endpoints: `POST /api/auth/register` (public self-signup → `viewer`),
`POST /api/auth/token` (login), `GET /api/auth/me`, and admin-only
`GET|POST /api/auth/users`, `PATCH /api/auth/users/{id}`.

### Roles & write permissions (reads: any authenticated user)

| Role              | Can write                                            |
|-------------------|------------------------------------------------------|
| `admin`           | **everything** (override)                            |
| `project_manager` | projects, tasks, resources, subcontractors, change orders |
| `accounting`      | budget, purchase orders, change orders               |
| `viewer`          | nothing (read-only)                                  |

### Demo users (seeded on first run — **dev only**)

| Email                          | Password    | Role            |
|--------------------------------|-------------|-----------------|
| admin@constructerp.dev         | admin123    | admin           |
| pm@constructerp.dev            | pm123       | project_manager |
| accounting@constructerp.dev    | acct123     | accounting      |
| viewer@constructerp.dev        | viewer123   | viewer          |

Disable seeding with `SEED_DEMO_USERS=false`. **Set a real `SECRET_KEY` in
production** (`export SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')"`).

## Switching to PostgreSQL

```bash
uv pip install "psycopg[binary]"
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/constructerp"
uv run uvicorn app.main:app
```

## Tests

```bash
uv run pytest -q
```

## Layout

```
backend/
├── app/
│   ├── config.py     # env-driven settings
│   ├── database.py   # engine, session, Base
│   ├── models.py     # SQLAlchemy ORM schema
│   ├── schemas.py    # Pydantic v2 request/response models
│   ├── crud.py       # generic CRUD router factory
│   ├── seed.py       # demo-data seeding
│   └── main.py       # FastAPI app + routers + /state
└── tests/test_api.py
```

## Next steps (not yet built)

- Alembic migrations (currently `create_all` on startup)
- Refresh tokens + token revocation / logout
- Wire the HTML frontend to this API (login screen + `fetch` replacing `localStorage`)
