# ConstructERP 🏗️

**Construction Project Management Suite** — a FastAPI backend with multi-tenancy, RBAC, file management, and AI agent capabilities.

![Version](https://img.shields.io/badge/version-0.5.0-amber)
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
cp backend/.env.example .env  # then set POSTGRES_PASSWORD + SECRET_KEY (both required)
docker compose up -d
# API at http://localhost:8000/docs

# For S3-compatible storage via the bundled MinIO, also set MINIO_ROOT_USER /
# MINIO_ROOT_PASSWORD (+ STORAGE_BACKEND=s3, S3_* ) in .env, then:
#   docker compose --profile s3 up -d   # MinIO console at http://localhost:9001
```

Compose intentionally has **no fallback values** for `POSTGRES_PASSWORD`,
`SECRET_KEY`, or the MinIO credentials — it errors out if they are unset, so a
deployment can never silently run on a weak, publicly-known secret.

The container entrypoint runs `alembic upgrade head` before serving, so the
Postgres schema is always brought up to date on deploy. **Set a stable
`SECRET_KEY`** in `.env` — it is required for production and mandatory if you run
more than one worker (`WORKERS>1`), otherwise JWTs signed by one worker are
rejected by another.

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
| POST | `/api/files/upload` | user | Upload file (records SHA-256 + storage backend/bucket) |
| GET | `/api/files` | user | List files |
| GET | `/api/files/{id}` | user | File metadata |
| GET | `/api/files/{id}/download` | user | Download file |
| DELETE | `/api/files/{id}` | user | Delete file |
| POST | `/api/files/presign-upload` | user | Pre-signed URL for direct-to-cloud upload (S3 backend) |
| POST | `/api/files/upload/init` · `/{id}/chunk` · `/{id}/complete` | user | Resumable chunked upload for large tender docs |
| POST | `/api/files/{id}/ocr` | PM | Extract text via OCR |
| POST | `/api/files/{id}/ingest` | user | Ingest → structured `extracted_data`; invoices create/link an EInvoice |
| GET | `/api/files/{id}/extracted` | user | Retrieve extracted structured data + linked entity |
| POST | `/api/raw/land` | user | Land an unstructured doc in the raw zone (pre-ETL) |
| POST | `/api/raw/presign` · `/{id}/confirm` | user | Direct-to-cloud landing with tracked manifest |
| POST | `/api/raw/{id}/etl` | user | Promote a landed doc into structured data |
| GET | `/api/raw` · `/{id}` · `/{id}/download` | user | List/inspect/download the landing zone |
| GET | `/api/ai/status` | user | AI agent availability |
| POST | `/api/ai/command` | user | NL command |
| POST | `/api/ai/analyze` | user | Budget analysis |
| GET | `/api/ai/briefing` | user | Morning briefing |
| POST | `/api/ai/chat` | user | Conversational chat |
| GET | `/api/health` | public | Health check |
| GET | `/api/state` | user | Full app state (single request) |

## Test Suite (69 tests)

Full end-to-end coverage across auth/RBAC, multi-tenancy, every domain module,
file storage (checksums, chunked upload, pre-signed URLs), the raw landing zone
(land → confirm → ETL → linked EInvoice, tenant isolation, idempotency), OCR,
and document ingestion. Run with `python -m pytest`.

## Data flow: raw landing zone → ETL → structured

Unstructured documents follow a two-tier (medallion) path so the original bytes
are preserved and processing state is separated from domain data:

```
upload / presign+confirm / chunked
        │
        ▼
  RAW ZONE (bronze)   raw/{tenant}/YYYY/MM/DD/uuid.ext   ← immutable
  raw_documents       etl_status: landed → extracting → extracted | failed
        │  POST /api/raw/{id}/etl   (reads raw read-only)
        ▼
  CURATED (silver)    FileUpload + EInvoice + extracted_data (JSON)
```

- **Land** unstructured data first: `POST /api/raw/land` (proxied) or
  `POST /api/raw/presign` → PUT to cloud → `POST /api/raw/{id}/confirm`. The
  manifest row is created up front, so direct-to-cloud objects are never
  orphaned. The landing zone is immutable — ETL never mutates or deletes it.
- **ETL**: `POST /api/raw/{id}/etl` promotes a landed doc into a curated
  `FileUpload` and runs the ingestion parser (OCR → classify → extract fields →
  link an `EInvoice` for invoices). Idempotent — safe to re-run.

## Storage & Ingestion

- **Unified storage layer** (`STORAGE_BACKEND=local|s3`) records a SHA-256
  checksum, backend, and bucket for every file. S3/MinIO/R2/Spaces are supported
  (set `S3_ENDPOINT` + `S3_FORCE_PATH_STYLE=true` for MinIO-style hosts). The raw
  landing zone shares the backend, isolated by the `RAW_PREFIX` (`raw/`) key
  prefix.
- **Direct-to-cloud uploads** via `POST /api/files/presign-upload` (pre-signed
  PUT), and **resumable chunked uploads** for large tender documents.
- **Ingestion pipeline**: `POST /api/files/{id}/ingest` runs OCR → classifies →
  extracts normalized fields into `extracted_data` (JSON), and for invoices
  creates and links an `EInvoice` domain record (`ingested_entity_type/id`).

## Configuration

See `backend/.env.example` for all options. Key settings:

- `DATABASE_URL` — SQLite (dev) or PostgreSQL (prod)
- `SECRET_KEY` — JWT signing key (auto-generated in dev, **required in prod**)
- `STORAGE_BACKEND` — `local` or `s3`; S3 uses `S3_BUCKET/KEY/SECRET/REGION/ENDPOINT` (+ `S3_FORCE_PATH_STYLE`)
- `S3_PRESIGNED_EXPIRY_SECONDS` — lifetime of pre-signed upload/download URLs
- `UPLOAD_CHUNK_SIZE_BYTES` / `MAX_CHUNKS_PER_UPLOAD` / `CHUNK_TTL_SECONDS` — chunked upload tuning
- `AI_PROVIDER` — `openai`, `ollama`, or `disabled`
- `SEED_DEMO_USERS` — seed demo accounts on startup
- `WORKERS` — uvicorn worker count (set `SECRET_KEY` if >1)

## License

MIT