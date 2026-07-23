# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately via GitHub Security Advisories
(**Security → Report a vulnerability**) rather than opening a public issue. We aim
to acknowledge within 72 hours.

---

## Hardening review — 2026-07-24

A full-backend security review was performed on the v0.6.0 API. No SQL injection,
RCE, SSRF, or path-traversal issues were found — the codebase uses the SQLAlchemy
ORM throughout, server-generated UUID storage keys, and role-gated AI routes. The
findings below concerned **authentication defaults and tenant isolation**, and are
addressed in this branch.

### Fixed

| ID | Severity | Issue | Fix |
|----|----------|-------|-----|
| **C1** | Critical | Demo users with well-known passwords (incl. two admins) were seeded by default (`seed_demo_users=True`) on every startup. | Default is now `False`, and demo seeding is **only** ever honoured on a SQLite dev/test database — never on Postgres. A warning is logged if enabled against a non-SQLite DB. |
| **C2** | Critical | Tenant isolation keyed off `tenant_id IS NULL` to mean "see all tenants". Because public self-registration mints active users with **no** tenant, anyone could register and read every tenant's data. | Cross-tenant visibility now keys off an explicit `is_admin(user)` check. A user with no tenant is *scoped* — they see only untenanted/shared rows, never another tenant's. Applied consistently across `crud`, `files`, and the raw landing zone. |
| **H1** | High | `tenant_id` was accepted from the request body on create/update; a scoped user could plant or move records into another tenant. | Non-admins can no longer set `tenant_id` — it is force-stamped from the authenticated user on create and stripped from updates. Admins may still target a tenant explicitly. |
| **M1** | Medium | The chunked/resumable upload path skipped the extension/MIME allowlist that single-shot and raw-zone uploads enforce. | `validate_file` is now enforced at chunked-upload init. |
| **M3** | Medium | `encryption.py` read `settings.encryption_key`, which did not exist on `Settings` (latent `AttributeError`). | `encryption_key` is now a first-class setting (empty ⇒ ephemeral dev key). |

Regression tests were added: `test_null_tenant_user_is_scoped_not_superuser`,
`test_non_admin_cannot_forge_tenant_id_on_write`, and `test_raw_tenant_isolation`.

### Operator responsibilities (production)

- **Never** set `SEED_DEMO_USERS=true` on a production database. Create the first
  admin out-of-band. If any instance was ever exposed with the demo accounts,
  **rotate/remove them immediately** — the passwords are public in this repo's
  git history.
- Set a stable **`SECRET_KEY`** (JWTs break across workers/restarts otherwise) and
  a stable **`ENCRYPTION_KEY`** before relying on two-bid financial-proposal
  encryption.
- Restrict **`CORS_ORIGINS`** to known front-end origins (default `*`).
- Put the API behind a gateway that enforces a **request-body size limit** and
  **rate-limits `/api/auth/token`** (no brute-force protection is built in).

### Not yet addressed (tracked, lower priority)

- No rate limiting / account lockout on login.
- Static PBKDF2 salt in `encryption.py` (only relevant once the encryption
  feature is wired to a route).
- Chunked-upload sessions are keyed by an unguessable UUID but do not re-check
  `uploaded_by` on each chunk/complete call.
