# AIConstructERP — Mesh Collaboration

## Project
AI-native construction ERP with unified entity system, graph relationships, activity streams, and dynamic attributes.

## Current State (v3.0.0)
- ✅ **Unified entity system** — 8 core tables replace 56 rigid tables
- ✅ **16 built-in entity types** — project, vendor, tender, contract, BOQ, bidder, defect, inspection, site diary, submittal, consultant RFP, cost plan, purchase request, RFQ, goods receipt, e-invoice
- ✅ **Dynamic attributes** — add fields at runtime, no migrations
- ✅ **Graph relationships** — any entity can relate to any other entity
- ✅ **Graph traversal** — depth-based queries across the entity graph
- ✅ **Activity stream** — auto-recorded on every create/update/relate
- ✅ **Threaded comments** — discussions on any entity
- ✅ **File attachments** — upload once, attach to any entity
- ✅ **JWT auth with RBAC** — 4 roles (admin, project_manager, accounting, viewer)
- ✅ **File storage** — local FS (dev) / S3 or MinIO (prod)
- ✅ **Custom fields** — JSON + tags on every entity
- ✅ **Demo data** — seeded on first run
- ✅ **Swagger docs** — auto-generated at /docs

## Architecture

```
backend/
├── app/
│   ├── config.py       # env-driven settings
│   ├── database.py     # engine, session, Base
│   ├── models.py       # 8 core tables (entity system)
│   ├── schemas.py      # Pydantic v2 schemas
│   ├── crud.py         # generic CRUD router factory
│   ├── main.py         # FastAPI app + all endpoints
│   ├── auth.py         # auth endpoints
│   ├── security.py     # JWT, password hashing, RBAC
│   ├── seed.py         # built-in types + demo data
│   └── filestore.py    # FileStore ABC (local/S3)
├── tests/
├── requirements.txt
└── README.md
```

## API Endpoints (30+)

| Method | Path | Description |
|---|---|---|
| GET/POST | `/api/entity-types` | List/create entity type definitions |
| GET | `/api/attribute-definitions` | List attribute definitions |
| POST | `/api/entities` | Create any entity with dynamic attributes |
| GET | `/api/entities` | List entities (filter by type, status, search) |
| GET | `/api/entities/{id}` | Get entity with all attributes |
| PATCH | `/api/entities/{id}` | Update entity and attributes |
| DELETE | `/api/entities/{id}` | Archive entity |
| POST | `/api/relationships` | Create graph edge |
| GET | `/api/relationships` | Query relationships |
| DELETE | `/api/relationships/{id}` | Deactivate relationship |
| POST | `/api/graph/traverse` | Depth-based graph traversal |
| GET | `/api/entities/{id}/activities` | Activity stream |
| POST | `/api/comments` | Add comment |
| GET | `/api/entities/{id}/comments` | List comments |
| POST | `/api/entities/{id}/files` | Attach file |
| GET | `/api/entities/{id}/files` | List attached files |
| POST | `/api/files/upload` | Upload file |
| GET | `/api/files/{id}/download` | Download file |
| POST | `/api/auth/token` | Login |
| POST | `/api/auth/register` | Self-signup |
| GET | `/api/health` | Health check |

## How to Collaborate
1. Pick a task from the roadmap below
2. Edit files in `backend/app/`
3. Test: `cd backend && uvicorn app.main:app --reload --port 8787`
4. Update this file when done

## Roadmap
- [ ] Frontend integration (login + entity CRUD UI)
- [ ] AI-powered entity summarization
- [ ] Embedding search across entities
- [ ] WebSocket for real-time activity stream
- [ ] Multi-tenancy isolation
- [ ] Alembic migrations
- [ ] Refresh tokens + token revocation
- [ ] CI/CD pipeline

## Agents
- **Hermes Agent** — primary developer, full tool access
