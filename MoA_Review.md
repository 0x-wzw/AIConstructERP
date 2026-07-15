# AI Construct ERP — Mixture-of-Agents Deep Review

**Date:** 2026-07-14
**Method:** 5 specialist agents → 1 synthesis layer
**Scope:** `/Users/admin/ConstructERP/` codebase, BRD requirements, Obsidian vault context

---

## Agent 1: Security Auditor

### Findings

**S1. CORS allow_credentials with wildcard origin (CRITICAL)**
`main.py:42-49` — `allow_origins=["*"]` combined with `allow_credentials=True` is explicitly forbidden by the CORS spec. Browsers reject it; if a browser didn't, it would allow any website to make authenticated cross-origin requests. Fix: either use explicit origin list OR set `allow_credentials=False` when origins is `*`.

```python
# current (broken):
allow_origins=["*"] if settings.cors_origins == "*" else [...],
allow_credentials=True,

# fix:
allow_credentials=settings.cors_origins != "*",
```

**S2. JWT token has no refresh mechanism (MEDIUM)**
`security.py:39-47` — Tokens expire after 60 minutes with no refresh flow. Users get a hard 401 after expiry with no way to renew without re-entering their password. For an ERP this is disruptive. Should implement a `/api/auth/refresh` endpoint that accepts a valid (or about-to-expire) token and returns a new one.

**S3. No rate limiting on auth endpoints (MEDIUM)**
`auth.py:49-64` — The `/api/auth/token` endpoint has no rate limiting. An attacker can brute-force passwords indefinitely. Should add slowapi or a simple in-memory limiter.

**S4. JWT payload doesn't include tenant_id (LOW)**
`security.py:41-46` — The token contains `sub` (user_id) and `role` but not `tenant_id`. The server does a DB lookup on every request to get the user's tenant_id. Including it in the token would eliminate one DB query per request, though it means token invalidation when tenant_id changes.

**S5. Password truncation to 72 bytes is silent (LOW)**
`security.py:27-28` — bcrypt's 72-byte cap is handled by truncating to `[:72]`, but the user is never informed. If someone sets a long passphrase, they can log in with a different 72-byte prefix. Should validate password length server-side and reject >72 bytes, or document the behavior.

**S6. File download has no Content-Disposition header (LOW)**
`files.py:131-138` — Downloads return `Response(content=content, media_type=...)` but no `Content-Disposition: attachment; filename="..."` header. Browsers may try to render the file inline instead of downloading, and the original filename is lost.

**S7. No CSRF protection (LOW for API, MEDIUM if cookie auth added)**
Currently uses Bearer tokens (not cookies), so CSRF isn't applicable. But if cookie-based auth is ever added, the wildcard CORS + credentials combination becomes exploitable.

**S8. AI agent routes allow any authenticated user (MEDIUM)**
`ai_routes.py` — All AI endpoints only require `get_current_active_user`, not a specific role. A viewer can call `/api/ai/command` and get AI-generated responses based on the full tenant data context. If AI commands can trigger writes (the system prompt says "create, update, delete"), a viewer could potentially execute destructive actions through the AI agent. Should restrict AI routes to PM/admin roles, or ensure AI command responses are advisory only (no direct execution).

---

## Agent 2: BRD Coverage Analyst

### Methodology
Extracted the BRD's 9 modules and 50+ required features. Mapped each to the current codebase (10 ORM models, 33 endpoints).

### Coverage Matrix

| BRD Module | Required Features | Codebase Coverage | Gap Severity |
|---|---|---|---|
| **1. Vendor Management** | Vendor registration, pre-qualification, performance evaluation | ❌ 0% — No vendor model, no registration flow, no performance tracking | **CRITICAL** |
| **2. Tender Management** | BOQ, cost estimates, tender documents, addendum, tenderer tracking, two-bid opening, e-bidding, reverse auction, public tender, tender reports, rate comparison, rates rationalisation, award recommendation | ❌ 0% — No tender model, no BOQ, no bid system | **CRITICAL** |
| **3. Contract Management** | Progress claims, variation management, payment certificates, final account | ~10% — `ChangeOrder` model partially covers variation orders. No progress claims, payment certificates, or final account | **HIGH** |
| **4. Consultant Management** | RFP management, consultant appointment | ❌ 0% | **HIGH** |
| **5. Cost Data Management** | Cost benchmarking, cost plan analysis, project rates analysis | ❌ 0% — BudgetItem tracks budget/committed/spent but no benchmarking, rate analysis, or cost plan comparison | **HIGH** |
| **6. Project Mgmt & CDE** | Project messaging, project forum, document management, submittals/approvals, defects management, inspection records, site diary | ~5% — FileUpload provides basic document management. No messaging, forum, submittals, defects, inspections, or site diary | **CRITICAL** |
| **7. Project Reports** | Customizable reporting, approval processes with attachments, reporting dashboard, automated email reminders | ❌ 0% — No reporting module, no email system, no approval workflow | **HIGH** |
| **8. General Procurement** | Cost codes, cost manager, budget approval, purchase request, RFQ, PO, goods receipt, e-invoice | ~20% — `PurchaseOrder` model + CRUD covers basic PO. No cost codes, budget approval workflow, RFQ, goods receipt, or e-invoice | **HIGH** |
| **9. Cloud-Based Access** | Cloud accessibility, centralized architecture | ✅ 80% — FastAPI + Docker + PostgreSQL provides this. Missing: multi-region, CDN, monitoring | **LOW** |

### Summary
- **Current BRD coverage: ~8%** (partial coverage in 2 of 9 modules)
- **4 modules have 0% coverage** (Vendor, Tender, Consultant, Reports)
- **2 modules are critically under-covered** (Tender Management and Project CDE are core to the BRD's value proposition)
- The current codebase is essentially a **generic construction project dashboard** (Projects + Tasks + Budget + POs + Subs), not the BuildSpace eProject ERP described in the BRD

### Key Missing Domain Objects (from BRD)
1. Vendor (registration, qualification, performance)
2. Tender (BOQ, tender documents, bids, addenda, awards)
3. Contract (claims, variations, payment certificates, final accounts)
4. Consultant (RFP, appointment)
5. CostPlan / RateItem (benchmarking, rate analysis)
6. Message/Forum (project communication)
7. Submittal (submittal/approval workflow)
8. Defect / Inspection (defect tracking, inspection records)
9. SiteDiary (daily site logs)
10. Report (customizable reports, approval workflow)
11. CostCode (procurement cost coding)
12. PurchaseRequest / RFQ / GoodsReceipt / EInvoice (procurement pipeline)
13. Approval (generic approval workflow with attachments)

---

## Agent 3: Code Quality & Architecture Reviewer

### Findings

**A1. `from __future__ import annotations` missing in models.py (HIGH)**
`models.py` uses `List["Task"]` and `Optional["Project"]` as string-quoted forward refs, which works. But it also uses `Mapped[List["Task"]]` — on Python 3.9, SQLAlchemy 2.0's MappedColumn needs real types at runtime to resolve. The current approach works because of the string quotes, but if anyone adds `Mapped[list[Task]]` (PEP 585), it will break on 3.9. Should either add `from __future__ import annotations` (already removed earlier to fix 3.9 compat — circular issue) or document that only `Optional[T]` / `List[T]` with string quotes is allowed. The real fix is to require Python 3.10+ in the Dockerfile (already set to 3.11-slim) and add `from __future__ import annotations` back. The 3.9 constraint is only for the local dev machine.

**A2. Storage backend instantiated at import time (MEDIUM)**
`files.py:27` — `storage = get_storage_backend()` runs at module import. If S3 settings are misconfigured, the entire app fails to start with an unhelpful ImportError or ValueError from S3Storage.__init__. Should defer to first request or wrap in a lazy singleton.

**A3. AI agent instantiated at import time (MEDIUM)**
`ai.py:168` — `ai_agent = AIAgent()` runs at import. If the `openai` library is installed but misconfigured, the import silently fails (the try/except swallows ImportError). The agent then reports "not configured" which is misleading. Should log a warning.

**A4. `ai_routes.py` calls `get_data_context` twice in `/analyze` (LOW)**
`ai_routes.py:86-95` — The `/analyze` endpoint calls `get_data_context(db, user)` and then extracts only the `"budget"` key. The full context (projects, POs, subs) is loaded but discarded. Should query budget directly:

```python
# current (wasteful):
budget_data = [{"category": b.category, ...} for b in get_data_context(db, user)["budget"]]

# fix:
from .crud import _tenant_filter
q = db.query(models.BudgetItem)
tf = _tenant_filter(models.BudgetItem, user)
if tf is not None:
    q = q.filter(tf)
budget_data = [{"category": b.category, "budget": float(b.budget), ...} for b in q.all()]
```

**A5. `/api/state` endpoint does N+1 queries (LOW)**
`main.py:121-147` — The `full_state` endpoint runs 7 separate queries (one per model). This is acceptable for small datasets but will degrade with scale. Could use a single query with joins for related models, or cache the result with a short TTL.

**A6. `generate_po_number` queries ALL purchase orders (LOW)**
`crud.py:133-148` — `db.query(PurchaseOrder.po_number).all()` loads every PO number into memory to find the max. For a system with thousands of POs, this is O(n). Should use `db.query(func.max(...))` or a sequence.

**A7. No soft delete on any entity (MEDIUM)**
All CRUD operations use `db.delete()` (hard delete). The BRD emphasizes audit trails. Construction ERPs typically require soft delete (archive) for compliance. The original Obsidian note mentioned soft delete on files, but the current codebase has none.

**A8. No audit/activity logging (HIGH)**
The BRD requires "audit trails" and "accountability." The current codebase has zero audit logging. Every create/update/delete should record who, what, when. The Obsidian note describes an `entity_activities` table that doesn't exist.

**A9. No database migrations (HIGH)**
`main.py:23` — `Base.metadata.create_all(bind=engine)` creates tables but never alters them. Any schema change (adding a column, changing a type) requires dropping the database. For a system intended for production use, Alembic migrations are essential. The `alembic` package isn't even in requirements.txt.

**A10. `files.py` imports unused modules (LOW)**
`files.py:1-2` — `import os` and `import tempfile` are imported but never used. Clean up.

**A11. No global exception handler (MEDIUM)**
No `@app.exception_handler(Exception)` registered. Unhandled exceptions return a raw 500 with a stack trace in the response body (in debug mode) or a generic error (in production). Should add a global handler that logs the error and returns a clean JSON response.

**A12. No structured request logging (MEDIUM)**
No request/response logging middleware. In production, there's no way to trace which user made which request. Should add a middleware that logs method, path, status, duration, and user_id.

---

## Agent 4: AI & Data Pipeline Analyst

### Findings

**D1. AI agent singleton never re-initializes (MEDIUM)**
`ai.py:168` — `ai_agent = AIAgent()` runs once at import. If the AI provider becomes available later (e.g., Ollama starts after the API), the agent remains "not configured" until the app is restarted. Should implement a `reinit()` method or check availability on each request.

**D2. AI command execution is advisory only — no enforcement (HIGH)**
`ai.py:63-87` — The `process_command` method returns a JSON dict with `action: "create"` and `data: {...}`, but nothing in the system actually executes that action. The AI says "create this project" but no project is created. This is either a design decision (advisory) or an unimplemented feature. If advisory, it should be clearly documented. If meant to execute, it needs a safe execution layer with RBAC enforcement.

**D3. AI data context leaks full project/budget data (MEDIUM)**
`ai_routes.py:27-61` — `get_data_context` sends the entire tenant's project, PO, budget, and subcontractor data to the LLM. This is a data privacy concern if using a third-party LLM (OpenAI). The data includes financial figures, supplier names, and contract values. Should consider:
- Sending only summaries/aggregates to the LLM
- Using a local model (Ollama) for sensitive data
- Adding a warning/consent flow for cloud LLM usage

**D4. No vector search / embeddings (MEDIUM)**
The Obsidian note describes `question_embedding` and `specs_embedding` for RFI/BIM vector search. The current codebase has no vector capabilities. The `FileUpload.ocr_text` field exists but is never populated (no OCR implementation despite the field existing).

**D5. OCR pipeline not implemented (MEDIUM)**
`models.py:164` — `ocr_text` and `ocr_processed` fields exist on `FileUpload`, and the `AIAgent` class has `ocr_document` and `_run_ocr` methods, but there's no route that triggers OCR. The `files.py` router has no `/api/files/{id}/ocr` endpoint. The OCR code in `ai.py` references `settings.tesseract_lang` which doesn't exist in `config.py`.

**D6. AI chat history is not persisted (LOW)**
`ai_routes.py:107-115` — Chat history is passed in the request body (`ChatRequest.history`) but never stored server-side. Each request is stateless. For a project management assistant, conversation history should be persisted per user/session.

**D7. No streaming for AI responses (LOW)**
All AI endpoints wait for the complete LLM response before returning. For long briefings or chat responses, this means the client waits 5-30 seconds with no feedback. Should implement SSE streaming for chat/briefing endpoints.

---

## Agent 5: Testing & DevOps Analyst

### Findings

**T1. Tests share a module-scoped fixture (MEDIUM)**
`test_api.py:15-18` — The `client` fixture is `scope="module"`, meaning all tests share the same database state. Tests are order-dependent: `test_seeded_reads` assumes seed data exists, `test_tenant_isolation_on_reads` creates tenants that persist for subsequent tests. If tests run in different order or in parallel, they'll fail. Should use function-scoped fixtures with database rollback or per-test temp DB.

**T2. No test for error cases (MEDIUM)**
The test suite covers happy paths and RBAC but doesn't test:
- Concurrent edits (optimistic locking)
- Invalid data types (string where int expected)
- SQL injection attempts via search query
- File upload with no filename
- File upload with path traversal in filename (`../../etc/passwd`)
- Very long filenames / payloads
- Rate limiting / brute force

**T3. No CI/CD pipeline (MEDIUM)**
No GitHub Actions, no pre-commit hooks, no linting config. The `.gitignore` exists but there's no automation for test running, linting, or building.

**T4. Docker Compose has hardcoded passwords (LOW)**
`docker-compose.yml` — PostgreSQL and MinIO use `constructerp:constructerp` and `minioadmin:minioadmin`. Should use `.env` file references: `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}`.

**T5. No health check for the API container (LOW)**
`docker-compose.yml` — The `api` service has no `healthcheck`. Docker can't determine if the API is ready. The `depends_on: db: condition: service_healthy` ensures DB readiness but not API readiness. Should add:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
  interval: 10s
  timeout: 5s
  retries: 3
```

**T6. No `.dockerignore` (LOW)**
No `.dockerignore` file. The Docker build context includes `__pycache__/`, `.pytest_cache/`, `constructerp.db`, `uploads/`, and other dev artifacts, inflating the image size.

**T7. Frontend not tested (LOW)**
The `frontend/` directory has `login.html`, `app.html`, and `api.js` but no tests. No Playwright/Cypress E2E tests.

**T8. Test coverage not measured (LOW)**
No `pytest-cov` or coverage report. Don't know what percentage of code is actually exercised by tests.

---

## Synthesis: Aggregated Gap Analysis

### Priority-Ordered Action List

#### 🔴 P0 — Must Fix Before Production

| # | Issue | Agent | Effort | Impact |
|---|---|---|---|---|
| 1 | CORS wildcard + credentials | S1 | 5min | Security: prevents credential theft |
| 2 | AI routes accessible to viewers | S8 | 10min | Security: viewers can trigger AI writes |
| 3 | No audit logging | A8 | 4h | Compliance: BRD requires audit trails |
| 4 | No database migrations (Alembic) | A9 | 2h | Operations: can't evolve schema in prod |
| 5 | No rate limiting on auth | S3 | 1h | Security: brute-force protection |
| 6 | File download missing Content-Disposition | S6 | 5min | UX: downloads work incorrectly |

#### 🟠 P1 — Should Fix Before Enterprise Use

| # | Issue | Agent | Effort | Impact |
|---|---|---|---|---|
| 7 | BRD coverage ~8% — 4 modules at 0% | BRD | 40-80h | Product: system doesn't meet BRD requirements |
| 8 | No Vendor Management module | BRD | 8h | Product: core BRD module missing |
| 9 | No Tender Management module | BRD | 16h | Product: core BRD module missing |
| 10 | No Contract Management beyond ChangeOrders | BRD | 12h | Product: claims/payment certs missing |
| 11 | No messaging/forum/CDE | BRD | 8h | Product: collaboration features missing |
| 12 | No soft delete | A7 | 4h | Data integrity: accidental data loss |
| 13 | No global exception handler | A11 | 1h | UX: unhandled errors leak stack traces |
| 14 | No structured logging | A12 | 2h | Operations: no observability |
| 15 | AI data context sends full data to LLM | D3 | 4h | Privacy: financial data to third parties |
| 16 | AI command advisory — no execution layer | D2 | 16h | Feature: AI is non-functional for actions |
| 17 | OCR pipeline not wired | D5 | 4h | Feature: ocr_text field never populated |
| 18 | Tests are order-dependent | T1 | 2h | Test reliability: flaky tests |
| 19 | JWT refresh tokens | S2 | 4h | UX: users get hard 401 every 60min |

#### 🟡 P2 — Should Fix Before Scale

| # | Issue | Agent | Effort | Impact |
|---|---|---|---|---|
| 20 | Storage/AI instantiated at import | A2,A3 | 1h | Resilience: app crashes on misconfig |
| 21 | PO number O(n) query | A6 | 30min | Performance: degrades with scale |
| 22 | `/api/state` does 7 queries | A5 | 1h | Performance: slow with large datasets |
| 23 | AI agent never re-initializes | D1 | 1h | UX: requires restart to detect AI |
| 24 | No CI/CD | T3 | 4h | DevOps: no automated quality gate |
| 25 | No `.dockerignore` | T6 | 5min | DevOps: image bloat |
| 26 | Docker healthcheck missing | T5 | 5min | DevOps: container readiness unknown |
| 27 | No test for edge cases / injection | T2 | 4h | Security: untested attack vectors |
| 28 | AI chat history not persisted | D6 | 4h | UX: stateless conversations |
| 29 | No streaming AI responses | D7 | 4h | UX: long waits with no feedback |
| 30 | Unused imports in files.py | A10 | 2min | Code hygiene |

#### 🟢 P3 — Nice to Have

| # | Issue | Agent | Effort | Impact |
|---|---|---|---|---|
| 31 | JWT includes tenant_id | S4 | 1h | Performance: save 1 DB query/request |
| 32 | Password truncation silent | S5 | 30min | UX: edge case |
| 33 | `from __future__` vs Python 3.9 | A1 | — | Tech debt: drop 3.9 support |
| 34 | AI `/analyze` loads full context | A4 | 10min | Performance: minor waste |
| 35 | Test coverage measurement | T8 | 1h | DevOps: visibility into coverage |
| 36 | Frontend tests | T7 | 8h | Quality: E2E coverage |
| 37 | Vector search / embeddings | D4 | 16h | Feature: semantic search (future) |

### BRD Gap Summary

```
Module 1: Vendor Management     [████░░░░░░░░░░░░░░░░]  0%  — CRITICAL
Module 2: Tender Management     [████░░░░░░░░░░░░░░░░]  0%  — CRITICAL
Module 3: Contract Management   [███░░░░░░░░░░░░░░░░░] 10%  — HIGH
Module 4: Consultant Management [████░░░░░░░░░░░░░░░░]  0%  — HIGH
Module 5: Cost Data Management  [█░░░░░░░░░░░░░░░░░░░]  5%  — HIGH
Module 6: Project CDE           [█░░░░░░░░░░░░░░░░░░░]  5%  — CRITICAL
Module 7: Project Reports       [████░░░░░░░░░░░░░░░░]  0%  — HIGH
Module 8: General Procurement   [████░░░░░░░░░░░░░░░░] 20%  — HIGH
Module 9: Cloud-Based Access    [████████████████░░░░] 80%  — LOW
```

The codebase covers Module 9 well (Docker, FastAPI, PostgreSQL). Module 8 has partial coverage (PurchaseOrder). Everything else is 0-10%. The system is approximately **8% BRD-compliant**.

---

*Generated by Mixture-of-Agents review — 5 specialist agents + 1 synthesis layer. All findings reference specific file paths and line numbers in the actual codebase.*