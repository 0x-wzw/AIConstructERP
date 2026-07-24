# Changelog

All notable changes to ConstructERP are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [0.7.0] — 2026-07-24

### Added
- **Malaysia LHDN MyInvois e-invoicing (scaffold).** A pluggable clearance layer
  (`EINVOICE_BACKEND=stub|direct`) mirroring the storage subsystem, so the
  transport is swappable and nothing hits the network by default. New per-line
  `e_invoice_lines` table, per-tenant `myinvois_config` (API client secret stored
  **encrypted**), and MyInvois fields on `e_invoices` — TIN/BRN/SST/MSIC, UUID,
  submission UID, validation link, status (Alembic migration `b3d9f1a26c47`).
  - Endpoints under `/api/einvoice`: admin-only config, line management, and the
    `submit → status → cancel` lifecycle plus `validate-tin`.
  - `app/einvoice/`: `backends.py` (offline `stub` default + `direct` LHDN),
    `client.py` (httpx OAuth2 + document APIs), `ubl_mapper.py` (UBL 2.1 JSON),
    `signer.py` (minify + SHA-256 + base64; XAdES signature is a placeholder with
    a hard guard that refuses to submit unsigned documents to production).
- **`encryption.encrypt_secret` / `decrypt_secret`** helpers; `ENCRYPTION_KEY` is
  now a first-class setting.
- **RFC 0001** (`docs/rfc/`) — plans a module registry/manifest architecture and a
  Document Control module (RFIs, drawing register, transmittals) for the next
  release.

### Security
- **Demo accounts are no longer seeded by default.** `SEED_DEMO_USERS` defaults to
  `false` and is only ever honoured on a **SQLite** dev/test database — never
  Postgres. The demo passwords are public in this repo; production must create its
  own admin out-of-band.
- **Tenant isolation fix (critical).** Cross-tenant visibility now keys off an
  explicit `is_admin()` check instead of `tenant_id IS NULL`. Previously a public
  self-registration (which has no tenant) could read **every** tenant's data;
  such users are now scoped to shared rows. Applied across CRUD, files, and the
  raw landing zone.
- **No forged `tenant_id` on writes** — non-admins can no longer set or move a
  record's `tenant_id`; it is stamped from the authenticated user.
- **Chunked upload** now enforces the same extension/MIME allowlist as the
  single-shot and raw-zone upload paths.
- **docker-compose has no weak secret fallbacks.** `POSTGRES_PASSWORD`,
  `SECRET_KEY`, and the MinIO credentials are required (`${VAR:?}`) — compose
  fails fast rather than running on a publicly-known default. (A static
  `SECRET_KEY` would let anyone forge admin JWTs.) MinIO moved behind an `s3`
  compose profile.

### Changed
- `.env.example` now ships `SEED_DEMO_USERS=false` and documents the required
  secrets + MyInvois settings.
- Shared pytest fixtures moved to `conftest.py`; the suite is now **75 tests**.

### Fixed
- `encryption.py` referenced an undefined `settings.encryption_key` (a latent
  `AttributeError`) — `encryption_key` is now a defined setting.

## [0.6.0] — 2026-07-22

### Added
- **Raw landing zone (bronze tier)** — a dedicated cloud staging area where
  unstructured documents land immutably *before* ETL turns them into structured
  data. Zoned by the `raw/` key prefix so it works identically on the local,
  S3, MinIO, and R2 backends (`RAW_PREFIX`). New `raw_documents` staging table
  tracks each landed object and its ETL state
  (`landed → extracting → extracted | failed`) independently of the curated
  `FileUpload` it produces (Alembic migration `a2f7c9d4e810`).
- New endpoints (`app/raw_routes.py`, `app/raw_store.py`):
  - `POST /api/raw/land` — proxy an unstructured file into the landing zone.
  - `POST /api/raw/presign` — issue a pre-signed PUT **and** pre-register the
    manifest row, so direct-to-cloud uploads are tracked from the moment the URL
    is issued.
  - `POST /api/raw/{id}/confirm` — verify a pre-signed upload actually landed
    (size + checksum), closing the orphaned-object gap.
  - `POST /api/raw/{id}/etl` — promote a landed doc into structured domain data,
    reusing the existing ingestion parser (idempotent; raw bytes never mutated).
  - `GET /api/raw`, `GET /api/raw/{id}`, `GET /api/raw/{id}/download`.

### Fixed
- Pre-signed direct-to-cloud uploads no longer strand objects with no DB row —
  the raw flow registers a manifest up front and confirms landing.
- Pre-signed uploads now validate file extension/size (previously bypassed).
- Field extraction no longer stamps a spurious `total_amount` on non-financial
  documents (blueprints, permits, photos).

## [0.5.0] — 2026-07-16

### Added
- **Unified cloud storage layer.** Every stored file now records a SHA-256
  checksum, its storage backend, and bucket. S3/MinIO/R2/Spaces supported via
  `S3_ENDPOINT` + `S3_FORCE_PATH_STYLE`.
- **Direct-to-cloud uploads** — `POST /api/files/presign-upload` returns a
  pre-signed PUT URL so large files upload straight to object storage.
- **Resumable chunked upload** for large tender documents
  (`/api/files/upload/init` · `/{id}/chunk` · `/{id}/complete`), now wired to the
  unified storage layer and the `FileUpload` model.
- **Document ingestion pipeline** — `POST /api/files/{id}/ingest` runs OCR,
  classifies the document, extracts normalized fields into `extracted_data`
  (JSON), and for invoices creates and links an `EInvoice` record. New
  `GET /api/files/{id}/extracted` returns the structured result.
- New `FileUpload` columns: `storage_bucket`, `checksum_sha256`, `ingest_status`,
  `extracted_data`, `ingested_entity_type/id`, `ingested_at`
  (Alembic migration `9a1c4e77b210`).
- Container entrypoint now runs `alembic upgrade head` before serving; Dockerfile
  installs `tesseract`/`poppler` for OCR and runs as a non-root user.

### Changed
- Postgres schema is owned by Alembic migrations; `create_all()` on startup is
  limited to SQLite (dev/test) so upgrades never silently miss new columns.
- `requirements.txt` now includes `boto3`, `psycopg[binary]`, and OCR libraries.
- `docker-compose`: uploads moved to a named volume; S3/MinIO and `WORKERS`
  wired through environment.

### Removed
- Deleted the redundant, broken `filestore.py` storage stack (it referenced a
  nonexistent `FileMetadata` model, an undefined `UploadResponse` schema, and six
  config settings that never existed, so the chunked uploader could not run).

### Fixed
- Chunked upload endpoint no longer crashes on import/first-call; its router is
  now registered in the app.

## [0.4.0] — 2026-07-15

- Full BRD coverage, React frontend, AI chat persistence, SSE streaming, OCR
  pipeline, reverse e-auction, final accounts, cost benchmarking, report
  templates, email reminders. CI lint fixes and repo hygiene (untracked uploads,
  version reconciliation).
