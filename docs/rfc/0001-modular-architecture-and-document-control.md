# RFC 0001 — Modular module architecture + Document Control

Status: **Proposed** · Target: next release (v0.7.0) · Author: engineering

## Summary

Two coupled pieces of work for the next release:

1. **Module contract + registry** — turn "modules" from a *convention* (BRD
   comments + 43 hardcoded wiring lines in `main.py`) into a *contract* every
   module must satisfy. This is the guardrail that keeps the ERP modular and
   on-mission as it grows.
2. **Document Control module** — the first feature built on the contract: RFIs,
   a Drawing Register with revision control, and Transmittals. It fills the
   largest construction-collaboration gap and reuses existing files/CDE/audit.

Non-goals (explicit anti-dilution): no HR/payroll, no CRM/marketing, no BIM
authoring or model viewer, no general ledger. The ERP stays focused on
**construction project delivery**; external systems are reached via *connectors*
(the `storage`/`einvoice` pluggable-backend pattern), never re-implemented.

---

## Part 1 — Module contract & registry

### Problem
`main.py` mounts ~10 routers and 30+ CRUD resources by hand. Every new module
edits that block, there is no per-tenant enablement, and boundaries are implicit.

### Design
A module is a self-contained package under `app/modules/<name>/` exposing a
manifest:

```python
# app/modules/document_control/manifest.py
MANIFEST = ModuleManifest(
    name="document_control",
    version="1.0",
    router=router,                     # APIRouter (mounted under /api)
    models=[RFI, Drawing, DrawingRevision, Transmittal, TransmittalItem],
    migrations=["c7a1..."],            # alembic revisions this module owns
    config_model=None,                 # optional per-tenant config (cf. MyInvoisConfig)
    adds_roles=[],                     # any new RBAC roles/capabilities
    depends_on=["files"],              # ordering + hard dependency check
    default_enabled=True,              # on for existing tenants (no regressions)
)
```

`app/module_registry.py` holds an explicit list of manifests (explicit >
import-magic for auditability), validates `depends_on`, and exposes
`enabled(tenant)`. `main.py` collapses to:

```python
for m in module_registry.enabled_for(tenant=None):
    app.include_router(m.router, prefix="/api")
```

### Per-tenant enablement
New table `tenant_modules(tenant_id, module_name, enabled)`; absence ⇒
`manifest.default_enabled`. Admin endpoints `GET/PUT /api/modules` to toggle.
This gives SaaS tiering for free and a kill-switch per module.

### Migration strategy (low-risk, incremental)
- Introduce the registry and route **new** modules (Document Control) through it.
- Keep existing routers working unchanged; optionally backfill them into
  manifests later as a pure refactor. **No behaviour change** to current
  endpoints in this release.
- `default_enabled=True` for every existing capability so no tenant loses access.

### Acceptance
- `main.py` mounts new modules via the registry; existing 75 tests stay green.
- Toggling a module off returns 404 for its routes for that tenant.
- Registry rejects a manifest whose `depends_on` is missing.

---

## Part 2 — Document Control module

Package `app/modules/document_control/`. Reuses `files`/`storage` for
attachments, `audit` for history, and the existing tenant/RBAC rules. CRUD uses
`make_crud_router` where a plain resource suffices; workflow actions are explicit
routes.

### Data model
- **RFI** — `rfi_no`, `project_id`, `subject`, `question`, `discipline`,
  `priority`, `status` (open|answered|closed), `raised_by`, `assigned_to`,
  `due_date`, `response`, `responded_by`, `responded_at`, `closed_at`,
  `cost_impact`/`time_impact` flags, `drawing_ref`, `tenant_id`, `is_archived`.
- **Drawing** (register) — `drawing_no`, `project_id`, `title`, `discipline`,
  `current_revision`, `status` (draft|for_review|approved|superseded),
  `current_file_id → file_uploads`, `scale`, `issued_date`, `tenant_id`,
  `is_archived`.
- **DrawingRevision** — `drawing_id`, `revision`, `file_id`, `issued_date`,
  `notes` (immutable history; supersede never overwrites).
- **Transmittal** — `transmittal_no`, `project_id`, `to_party`, `from_party`,
  `issue_date`, `purpose` (for_approval|for_construction|for_info),
  `status` (draft|issued|acknowledged), `acknowledged_at`, `tenant_id`.
- **TransmittalItem** — `transmittal_id`, `drawing_id`/`file_id`, `copies`,
  `format`.

### Endpoints (`/api/rfis`, `/api/drawings`, `/api/transmittals`)
- RFI: CRUD + `POST /rfis/{id}/respond`, `POST /rfis/{id}/close`.
- Drawing: CRUD + `POST /drawings/{id}/revise` (upload a new rev → new
  DrawingRevision, bump `current_revision`, previous → superseded). Reuses the
  file-upload path.
- Transmittal: CRUD + `POST /transmittals/{id}/issue`,
  `POST /transmittals/{id}/acknowledge`.

### RBAC
Project managers manage; accounting/viewer read-only (via `require_roles(PM)` on
writes, matching existing conventions). Tenant isolation via the standard
`is_admin`/tenant-filter helpers.

### Acceptance
- Revising a drawing preserves prior revisions and marks them superseded.
- RFI lifecycle open → answered → closed enforced (can't close an open RFI
  without a response).
- Transmittal issue/acknowledge transitions recorded in the audit log.
- Full tenant isolation + RBAC tests, all on the offline path (no new deps).

---

## Rollout (three PRs)

1. **Foundation** — `ModuleManifest` + `module_registry` + `tenant_modules`
   table + `/api/modules` admin toggle; register one existing capability as a
   proof-point. (No user-facing behaviour change.)
2. **Document Control models + migration** — the five tables via one Alembic
   revision, mounted through the registry.
3. **Workflows + tests** — RFI respond/close, drawing revise, transmittal
   issue/acknowledge, and the test suite.

## Risks
- *Hiding existing features* — mitigated by `default_enabled=True` + explicit
  backfill-later stance.
- *SQLite/Postgres parity* — every migration ships `server_default`s and is
  verified up **and** down (as with `b3d9f1a26c47`).
- *Scope creep inside Document Control* — drawing *viewing/markup* and BIM are
  explicitly out; this module is register + workflow + file linkage only.

## Future modules (backlog, same contract)
Payments/Retention/Cashflow · Scheduling (CPM/EVM) · HSE + Quality (NCR/ITP) ·
Accounting connector (AutoCount/SQL Account/Xero) · CIDB connector ·
Notifications hub (webhook/Slack/Teams/WhatsApp). Each must ship as a module
manifest; anything that can't is a sign it doesn't belong in the core.
