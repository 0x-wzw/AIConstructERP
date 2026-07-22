# Changelog

All notable changes to ConstructERP are documented here. This project follows
[Semantic Versioning](https://semver.org/).

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
