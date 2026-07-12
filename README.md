# AIConstructERP 🏗️🤖

**AI-Native Construction Project Management Suite** — a unified entity system with dynamic attributes, graph relationships, activity streams, and AI-ready context.

![Version](https://img.shields.io/badge/version-3.0.0-amber)
![Status](https://img.shields.io/badge/status-ai--native-green)

## Architecture

Instead of 56 rigid tables, AIConstructERP uses a **unified entity system**:

```
┌─────────────────────────────────────────────────────────┐
│                    ENTITY SYSTEM                         │
├─────────────────────────────────────────────────────────┤
│  entity_types        — Schema definitions (16 built-in)  │
│  attribute_definitions — Field definitions per type      │
│  entities            — ALL domain objects (one table)    │
│  entity_attributes   — Dynamic key-value fields          │
│  entity_relationships — Graph edges (any→any)            │
│  entity_activities   — Activity/audit stream             │
│  entity_comments     — Threaded discussions              │
│  entity_files        — File attachments                  │
├─────────────────────────────────────────────────────────┤
│  users               — Auth (JWT, RBAC)                  │
│  file_metadata       — File storage (local FS or S3)     │
└─────────────────────────────────────────────────────────┘
```

### Key Capabilities

- **Zero-migration field additions** — just POST an attribute
- **New entity types at runtime** — POST to `/api/entity-types`
- **Graph traversal** — find all vendors for a project, all tenders a vendor bid on
- **Activity stream** — every state change auto-recorded for audit & AI context
- **Threaded comments** — discussions on any entity
- **File attachments** — upload once, attach anywhere
- **Multi-tenancy** — `tenant_id` on every entity
- **AI-ready** — `summary`, `ai_embedding_id`, full activity history

## 16 Built-in Entity Types

| Type | Attributes |
|---|---|
| **Project** | location, budget, duration, progress, start/end dates, description |
| **Vendor** | registration_no, tax_id, contact, email, phone, category, classification, pre-qualified |
| **Tender** | description, category, open/close dates, budget estimate, currency |
| **Contract** | description, contract value, start/end dates |
| **BOQ Item** | item_no, description, unit, quantity, rate estimate, category |
| **Bidder** | bid amount, technical/financial/total scores, submission time |
| **Defect** | description, location, severity, assigned to, target resolution |
| **Inspection** | description, location, type, scheduled date, result |
| **Site Diary** | entry date, weather, temperature, work summary, issues, safety, labour count |
| **Submittal** | description, category, review comments, due date |
| **Consultant RFP** | description, scope of work, category, open/close dates, budget |
| **Cost Plan** | version, total estimated/approved, notes |
| **Purchase Request** | description, notes |
| **RFQ** | description, response deadline |
| **Goods Receipt** | supplier, delivery note, received date, notes |
| **E-Invoice** | supplier, invoice/due dates, total/tax/net amounts |

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI + SQLAlchemy |
| **Database** | SQLite (dev) / PostgreSQL (prod) |
| **Auth** | JWT (OAuth2 password flow) with RBAC |
| **File Storage** | Local FS (dev) / S3 or MinIO (prod) |
| **Frontend** | Vanilla JS + Tailwind CSS + Chart.js (included) |

## Quick Start

```bash
cd backend
pip install -r requirements.txt
rm -f constructerp.db
uvicorn app.main:app --reload --port 8787
```

Then open:
- **Swagger UI:** http://localhost:8787/docs
- **Health:** http://localhost:8787/api/health

### Demo Users

| Email | Password | Role |
|---|---|---|
| admin@constructerp.dev | admin123 | admin |
| pm@constructerp.dev | pm123 | project_manager |
| accounting@constructerp.dev | acct123 | accounting |
| viewer@constructerp.dev | viewer123 | viewer |

## API Overview

| Endpoint | Purpose |
|---|---|
| `POST/GET /api/entity-types` | Metamodel management |
| `POST/GET/PATCH/DELETE /api/entities` | Universal CRUD with dynamic attributes |
| `POST/GET/DELETE /api/relationships` | Graph edge management |
| `POST /api/graph/traverse` | Graph traversal (depth-based) |
| `GET /api/entities/{id}/activities` | Activity stream |
| `POST/GET /api/comments` | Threaded comments |
| `POST/GET /api/entities/{id}/files` | File attachments |
| `POST/GET/DELETE /api/files/upload` | File upload/download |

## License

MIT
